"""Run the frozen comparison protocol on the model before adaptation."""

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


def evaluate(dataset: Path, cache_dir: Path) -> dict:
    content = dataset.read_text(encoding="utf-8")
    cases = [json.loads(line) for line in content.splitlines()]
    if not cases or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("The dataset must be nonempty and have unique IDs.")

    start = perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_ID, revision=REVISION, cache_dir=cache_dir, local_files_only=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, revision=REVISION, cache_dir=cache_dir, local_files_only=True,
        dtype=torch.bfloat16, device_map={"": "cuda:0"},
    ).eval()
    generation = GenerationConfig(
        do_sample=False,
        max_new_tokens=MAX_NEW_TOKENS,
        eos_token_id=model.generation_config.eos_token_id,
        pad_token_id=model.generation_config.pad_token_id,
    )
    eos = generation.eos_token_id
    eos_ids = {eos} if isinstance(eos, int) else set(eos)

    predictions = []
    for case in cases:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": case["statement"]},
        ]
        inputs = tokenizer.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True,
            return_tensors="pt", return_dict=True,
        ).to(model.device)
        with torch.inference_mode():
            full = model.generate(**inputs, generation_config=generation)
        tokens = full[0, inputs["input_ids"].shape[1]:].tolist()
        ended = bool(tokens) and tokens[-1] in eos_ids
        raw = tokenizer.decode(
            tokens[:-1] if ended else tokens,
            skip_special_tokens=False, clean_up_tokenization_spaces=False,
        )
        if ended:
            score = verify_lp(raw, case["reference"])
        else:
            score = dict.fromkeys(CHECKS, False)
            score["issues"] = ["Generation reached the token limit without EOS."]
        predictions.append({
            "id": case["id"],
            "raw_response": raw,
            "generated_tokens": len(tokens),
            "ended_with_eos": ended,
            **score,
        })
        print(f"{case['id']}: JSON={score['format']}, formulation={score['formulation']}", flush=True)

    return {
        "dataset": dataset.as_posix(),
        "dataset_sha256_utf8_lf": sha256(content.encode("utf-8")).hexdigest(),
        "model": MODEL_ID,
        "revision": REVISION,
        "dtype": str(model.dtype),
        "gpu": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "scipy": scipy.__version__,
        "system_prompt": SYSTEM_PROMPT,
        "generation": generation.to_diff_dict(),
        "elapsed_seconds": round(perf_counter() - start, 2),
        "total": len(predictions),
        "scores": {key: sum(row[key] for row in predictions) for key in CHECKS},
        "predictions": predictions,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("data/human_test.jsonl"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".hf_cache/hub"))
    parser.add_argument("--output", type=Path, default=Path("runs/base_independent_v1.json"))
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"{args.output} already exists. Choose a new --output.")
    result = evaluate(args.dataset, args.cache_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"{result['scores']} out of {result['total']} -> {args.output}")


if __name__ == "__main__":
    main()
