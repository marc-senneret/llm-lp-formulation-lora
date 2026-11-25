"""Train Qwen with LoRA using the frozen train and validation splits."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import random
from time import perf_counter

import torch
import transformers
from torch.nn.utils.rnn import pad_sequence
from transformers import AutoModelForCausalLM, AutoTokenizer

from lp_llm.evaluate import MODEL_ID, REVISION, SYSTEM_PROMPT

IGNORE = -100


def load_split(path: Path, manifest: dict) -> list:
    content = path.read_text(encoding="utf-8")
    expected = manifest["files"][path.name]
    if sha256(content.encode("utf-8")).hexdigest() != expected["sha256"]:
        raise ValueError(f"{path}: differs from the frozen corpus manifest")
    rows = [json.loads(line) for line in content.splitlines()]
    if len(rows) != expected["examples"] or not rows or any(row["split"] != path.stem for row in rows):
        raise ValueError(f"{path}: unexpected count or split label")
    return rows


def encode_example(tokenizer, row: dict, max_length: int) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": row["statement"]},
    ]
    target = json.dumps(row["reference"], allow_nan=False)
    full = [*messages, {"role": "assistant", "content": target}]
    prompt_ids = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_dict=True,
    )["input_ids"]
    ids = tokenizer.apply_chat_template(
        full, tokenize=True, add_generation_prompt=False, return_dict=True,
    )["input_ids"]
    if ids[:len(prompt_ids)] != prompt_ids:
        raise ValueError(f"{row['id']}: prompt tokens are not a prefix of the full conversation")
    end = ids.index(tokenizer.eos_token_id, len(prompt_ids))
    if tokenizer.decode(ids[len(prompt_ids):end], clean_up_tokenization_spaces=False) != target:
        raise ValueError(f"{row['id']}: supervised tokens do not decode to the reference JSON")
    ids = ids[:end + 1]
    if len(ids) > max_length:
        raise ValueError(f"{row['id']}: {len(ids)} tokens exceed the limit of {max_length}")
    return {"input_ids": ids, "labels": [IGNORE] * len(prompt_ids) + ids[len(prompt_ids):],
            "prompt_length": len(prompt_ids)}


def make_batch(examples: list, pad_id: int) -> dict:
    ids = [torch.tensor(row["input_ids"], dtype=torch.long) for row in examples]
    labels = [torch.tensor(row["labels"], dtype=torch.long) for row in examples]
    return {
        "input_ids": pad_sequence(ids, batch_first=True, padding_value=pad_id),
        "attention_mask": pad_sequence([torch.ones_like(row) for row in ids], batch_first=True),
        "labels": pad_sequence(labels, batch_first=True, padding_value=IGNORE),
    }


def inspect_mask(tokenizer, rows: list, examples: list) -> None:
    shortest = min(range(len(examples)), key=lambda i: len(examples[i]["input_ids"]))
    longest = max(range(len(examples)), key=lambda i: len(examples[i]["input_ids"]))
    batch = make_batch([examples[shortest], examples[longest]], tokenizer.pad_token_id)
    for row_index, example_index in enumerate((shortest, longest)):
        labels = batch["labels"][row_index]
        ids = batch["input_ids"][row_index]
        attention = batch["attention_mask"][row_index]
        trained = labels != IGNORE
        prompt_tokens = examples[example_index]["prompt_length"]
        supervised = ids[trained].tolist()
        reference = rows[example_index]["reference"]
        if (trained[:prompt_tokens].any() or not (labels[~attention.bool()] == IGNORE).all()
                or not torch.equal(ids[trained], labels[trained])
                or supervised[-1] != tokenizer.eos_token_id
                or json.loads(tokenizer.decode(supervised[:-1])) != reference):
            raise ValueError(f"{rows[example_index]['id']}: invalid loss mask")
        print(f"{rows[example_index]['id']}: prompt={prompt_tokens}, "
              f"supervised={len(supervised)}, padding={int((attention == 0).sum())}")
        print(tokenizer.decode(supervised, clean_up_tokenization_spaces=False))


def train_adapter(train: list, validation: list, tokenizer, config: dict, cache: Path,
                  output: Path, fingerprint: str) -> None:
    from peft import LoraConfig, __version__ as peft_version, get_peft_model

    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("This configuration expects a CUDA GPU with BF16 support.")
    torch.manual_seed(config["seed"])
    order_rng = random.Random(config["seed"])
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, revision=REVISION, cache_dir=cache, local_files_only=True,
        dtype=torch.bfloat16, device_map={"": "cuda:0"},
    )
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(
        **config["lora"], bias="none", task_type="CAUSAL_LM", revision=REVISION,
    ))
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.print_trainable_parameters()
    trainable = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=config["learning_rate"])
    group_size = config["gradient_accumulation_steps"]
    training_rows = [(row, len(row["labels"]) - row["prompt_length"]) for row in train]
    validation_rows = [(row, len(row["labels"]) - row["prompt_length"]) for row in validation]
    total_train_tokens = sum(tokens for _, tokens in training_rows)
    total_validation_tokens = sum(tokens for _, tokens in validation_rows)

    def loss_for(row):
        batch = {key: tensor.to(model.device)
                 for key, tensor in make_batch([row], tokenizer.pad_token_id).items()}
        return model(**batch).loss

    history = []
    step = 0
    start = perf_counter()
    torch.cuda.reset_peak_memory_stats()
    for epoch in range(config["epochs"]):
        model.train()
        order = list(training_rows)
        order_rng.shuffle(order)
        training_nll = 0.0
        for offset in range(0, len(order), group_size):
            group = order[offset:offset + group_size]
            tokens = sum(count for _, count in group)
            optimizer.zero_grad(set_to_none=True)
            loss_sum = torch.zeros((), device=model.device)
            for row, count in group:
                weighted_loss = loss_for(row) * count
                (weighted_loss / tokens).backward()
                loss_sum += weighted_loss.detach()
            torch.nn.utils.clip_grad_norm_(trainable, config["max_grad_norm"], error_if_nonfinite=True)
            optimizer.step()
            step += 1
            group_nll = loss_sum.item()
            training_nll += group_nll
            print(f"epoch={epoch + 1} step={step} train_loss={group_nll / tokens:.4f}", flush=True)

        model.eval()
        with torch.inference_mode():
            validation_nll = sum(loss_for(row).item() * count for row, count in validation_rows)
        metrics = {
            "epoch": epoch + 1,
            "optimizer_steps": step,
            "train_loss": training_nll / total_train_tokens,
            "validation_loss": validation_nll / total_validation_tokens,
        }
        history.append(metrics)
        print(json.dumps(metrics, allow_nan=False), flush=True)

    output.mkdir(parents=True, exist_ok=False)
    model.save_pretrained(output)
    run = {
        "model": MODEL_ID, "revision": REVISION, "system_prompt": SYSTEM_PROMPT,
        "corpus_manifest_sha256_utf8_lf": fingerprint,
        "config": config, "train_examples": len(train), "validation_examples": len(validation),
        "trainable_parameters": sum(parameter.numel() for parameter in trainable),
        "torch": torch.__version__, "transformers": transformers.__version__,
        "peft": peft_version, "gpu": torch.cuda.get_device_name(0),
        "elapsed_seconds": round(perf_counter() - start, 2),
        "peak_vram_bytes": torch.cuda.max_memory_allocated(),
        "history": history,
    }
    (output / "training.json").write_text(json.dumps(run, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"Adapter saved to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/sft_lora.json"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".hf_cache/hub"))
    parser.add_argument("--output", type=Path, default=Path("runs/lora_v1"))
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not args.check_only and args.output.exists():
        parser.error("Output directory already exists. Choose a new --output.")

    manifest_text = (args.data_dir / "corpus_v1_manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    if manifest["preview"] is not False:
        parser.error("Training requires the final corpus manifest.")
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if min(config["epochs"], config["gradient_accumulation_steps"], config["max_sequence_length"]) < 1:
        parser.error("Epochs, accumulation and maximum sequence length must be positive.")
    train_rows = load_split(args.data_dir / "train.jsonl", manifest)
    validation_rows = load_split(args.data_dir / "validation.jsonl", manifest)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID, revision=REVISION, cache_dir=args.cache_dir, local_files_only=True,
    )
    limit = config["max_sequence_length"]
    train = [encode_example(tokenizer, row, limit) for row in train_rows]
    validation = [encode_example(tokenizer, row, limit) for row in validation_rows]
    inspect_mask(tokenizer, train_rows, train)
    print(f"Checked {len(train)} train and {len(validation)} validation examples.")
    if not args.check_only:
        train_adapter(train, validation, tokenizer, config, args.cache_dir, args.output,
                      sha256(manifest_text.encode("utf-8")).hexdigest())


if __name__ == "__main__":
    main()
