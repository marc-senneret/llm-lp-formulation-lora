"""Run the frozen comparison protocol with or without a LoRA adapter."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

import scipy
import torch
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer, GenerationConfig

from lp_llm.verify import verify_lp

MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
REVISION = "989aa7980e4cf806f80c7fef2b1adb7bc71aa306"
MAX_NEW_TOKENS = 256
CHECKS = ("format", "formulation", "solve", "reference")

SYSTEM_PROMPT = """Formulate the problem in the statement. Return only one JSON
object, with no markdown or explanation. Use exactly these keys:
- "variables": ["x1", "x2"].
- "objective": an object with "sense" ("min" or "max") and "coefficients"
  (two numbers, in x1, x2 order).
- "constraints": an array of two or three objects, each with "coefficients"
  (two numbers, in x1, x2 order), "sense" ("<=", ">=", or "="), and "rhs"
  (a number). Include every stated constraint apart from variable bounds.
- "bounds": one [lower, upper] pair per variable in x1, x2 order. Use null
  for an unbounded upper endpoint.
Use the units of the statement and keep each variable's stated meaning."""


def evaluate(dataset: Path, cache_dir: Path, adapter: Path | None = None, batch_size: int = 1) -> dict:
    if batch_size < 1:
        raise ValueError("Batch size must be positive.")
    content = dataset.read_text(encoding="utf-8")
    cases = [json.loads(line) for line in content.splitlines()]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("The dataset must be nonempty and have unique IDs.")
    if adapter is not None and not (adapter / "adapter_config.json").is_file():
        raise ValueError(f"No saved PEFT adapter found in {adapter}.")

    start = perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID, revision=REVISION, cache_dir=cache_dir, local_files_only=True,
    )
    tokenizer.padding_side = "left"
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, revision=REVISION, cache_dir=cache_dir, local_files_only=True,
        dtype=torch.bfloat16, device_map={"": "cuda:0"},
    )
    if adapter is not None:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, str(adapter.resolve()))
    model.eval()
    generation = GenerationConfig(
        do_sample=False,
        max_new_tokens=MAX_NEW_TOKENS,
        eos_token_id=model.generation_config.eos_token_id,
        pad_token_id=model.generation_config.pad_token_id,
    )
    eos = generation.eos_token_id
    eos_ids = {eos} if isinstance(eos, int) else set(eos)

    predictions = []
    for offset in range(0, len(cases), batch_size):
        group = cases[offset:offset + batch_size]
        messages = [
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": case["statement"]},
            ]
            for case in group
        ]
        inputs = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, padding=True,
            return_tensors="pt", return_dict=True,
        ).to(model.device)
        with torch.inference_mode():
            full = model.generate(**inputs, generation_config=generation)
        completions = full[:, inputs["input_ids"].shape[1]:].tolist()
        for case, tokens in zip(group, completions, strict=True):
            end = next((index for index, token in enumerate(tokens) if token in eos_ids), len(tokens))
            ended = end < len(tokens)
            raw = tokenizer.decode(
                tokens[:end], skip_special_tokens=False, clean_up_tokenization_spaces=False,
            )
            if ended:
                score = verify_lp(raw, case["reference"])
            else:
                score = dict.fromkeys(CHECKS, False)
                score["issues"] = ["Generation reached the token limit without EOS."]
            predictions.append({
                "id": case["id"],
                "raw_response": raw,
                "generated_tokens": end + int(ended),
                "ended_with_eos": ended,
                **score,
            })
            print(f"{case['id']}: JSON={score['format']}, formulation={score['formulation']}", flush=True)

    return {
        "dataset": dataset.as_posix(),
        "dataset_sha256_utf8_lf": sha256(content.encode("utf-8")).hexdigest(),
        "model": MODEL_ID,
        "revision": REVISION,
        "adapter": adapter.as_posix() if adapter is not None else None,
        "dtype": str(model.dtype),
        "gpu": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "scipy": scipy.__version__,
        "system_prompt": SYSTEM_PROMPT,
        "generation": generation.to_diff_dict(),
        "batch_size": batch_size,
        "elapsed_seconds": round(perf_counter() - start, 2),
        "total": len(predictions),
        "scores": {key: sum(row[key] for row in predictions) for key in CHECKS},
        "predictions": predictions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/human_test.jsonl"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".hf_cache/hub"))
    parser.add_argument("--adapter", type=Path)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.adapter is not None and args.output is None:
        parser.error("Provide --output when evaluating an adapter.")
    args.output = args.output or Path("runs/base_independent_v1.json")
    if args.output.exists():
        parser.error(f"{args.output} already exists. Choose a new --output.")
    if args.batch_size < 1:
        parser.error("Batch size must be positive.")
    result = evaluate(args.dataset, args.cache_dir, args.adapter, args.batch_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"{result['scores']} out of {result['total']} -> {args.output}")


if __name__ == "__main__":
    main()
