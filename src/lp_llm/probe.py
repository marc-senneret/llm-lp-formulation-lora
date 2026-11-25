"""Teacher-forced probe of the constraint-sense decision.

For every constraint of every reference, read the probability of the reference
sense token (' ">' or ' "<') given the exact reference prefix, with and without
the repetition penalty that generation inherits from Qwen's generation config.
"""

import argparse
import json
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from lp_llm.evaluate import MODEL_ID, REVISION
from lp_llm.train import encode_example

DATASETS = {"train": "data/train.jsonl", "validation": "data/validation.jsonl",
            "test": "data/test.jsonl", "human": "data/human_test.jsonl"}


def penalize(logits: torch.Tensor, prefix: torch.Tensor, penalty: float) -> torch.Tensor:
    """Same rule as transformers' RepetitionPenaltyLogitsProcessor, prompt included."""
    seen = prefix.unique()
    scores = logits[seen]
    logits = logits.clone()
    logits[seen] = torch.where(scores < 0, scores * penalty, scores / penalty)
    return logits


def probe_rows(model, tokenizer, rows: list, ge: int, le: int, penalty: float) -> list:
    out = []
    for row in rows:
        example = encode_example(tokenizer, row, 1024)
        ids = torch.tensor(example["input_ids"], device=model.device)
        positions = [i for i in range(example["prompt_length"], len(ids)) if ids[i] in (ge, le)]
        senses = [c["sense"] for c in row["reference"]["constraints"]]
        if len(positions) != len(senses):
            raise ValueError(f"{row['id']}: sense tokens do not match the reference constraints")
        with torch.inference_mode():
            logits = model(input_ids=ids[None]).logits[0].float()
        for k, (position, sense) in enumerate(zip(positions, senses)):
            target = ge if sense == ">=" else le
            record = {"id": row["id"], "family": row["family"],
                      "template_id": row.get("template_id"), "index": k, "sense": sense}
            for name, scores in (("raw", logits[position - 1]),
                                 ("penalized", penalize(logits[position - 1], ids[:position], penalty))):
                probabilities = torch.softmax(scores, -1)
                record[name] = {"p_ref": probabilities[target].item(),
                                "p_ge": probabilities[ge].item(), "p_le": probabilities[le].item(),
                                "argmax_is_ref": int(scores.argmax()) == target}
            out.append(record)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--splits", nargs="+", default=list(DATASETS))
    parser.add_argument("--penalty", type=float, default=1.1)
    parser.add_argument("--cache-dir", type=Path, default=Path(".hf_cache/hub"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from peft import PeftModel

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=REVISION, cache_dir=args.cache_dir,
                                              local_files_only=True)
    ge, le = (tokenizer.convert_tokens_to_ids(tokenizer.tokenize(t))[0] for t in (' ">', ' "<'))
    base = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision=REVISION, cache_dir=args.cache_dir,
                                                local_files_only=True, dtype=torch.bfloat16,
                                                device_map={"": "cuda:0"})
    model = PeftModel.from_pretrained(base, str(args.adapter.resolve())).eval()
    result = {"model": MODEL_ID, "revision": REVISION, "adapter": args.adapter.as_posix(),
              "penalty": args.penalty, "splits": {}}
    for split in args.splits:
        rows = [json.loads(line) for line in Path(DATASETS[split]).read_text(encoding="utf-8").splitlines()]
        with model.disable_adapter():
            base_records = probe_rows(model, tokenizer, rows, ge, le, args.penalty)
        lora_records = probe_rows(model, tokenizer, rows, ge, le, args.penalty)
        result["splits"][split] = {"base": base_records, "lora": lora_records}
        print(f"{split}: {len(lora_records)} sense positions", flush=True)
    args.output.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
