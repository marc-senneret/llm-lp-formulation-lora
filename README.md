# LP formulation with a LoRA-tuned LLM

Translate short English word problems into linear programmes (JSON), let a solver solve them, and measure what supervised LoRA fine-tuning changes. The model formulates; SciPy `linprog` (HiGHS) solves and verifies.

Scope is deliberately small: two non-negative continuous variables, two or three constraints, two families (production / profit maximisation with caps, and mixing / cost minimisation with minimum requirements). A null or negative result was considered acceptable.

Detailed reports and the project log are in French: [results](reports/results.md), [diagnostic](reports/diagnostic_sens_contraintes.md), [learning notes](reports/learning_notes.md), [French README](README.fr.md).

## Results (v1, executed)

`Qwen/Qwen2.5-1.5B-Instruct` (pinned revision `989aa79`), LoRA r=16 on the attention projections (0.28 % of parameters), one epoch on 300 examples, 19 optimiser steps, 4 min 15 s on a single RTX 4060 (8 GB).

Strict scoring: same prompt, same greedy decoding and same statements before and after; no output repair; any invalid output counts as a failure.

| Metric | Synthetic test, base | Synthetic test, LoRA | Independent set, base | Independent set, LoRA |
| --- | ---: | ---: | ---: | ---: |
| Schema-valid JSON | 0/80 | 77/80 | 0/20 | 18/20 |
| Exact formulation | 0/80 | 35/80 | 0/20 | 5/20 |
| Predicted problem solved | 0/80 | 77/80 | 0/20 | 17/20 |
| Optimal on the reference problem | 0/80 | 37/80 | 0/20 | 8/20 |

The base model wraps almost every answer in Markdown fences despite the instruction. With the fences stripped (diagnostic only, not the official score), it reaches 10/80 and 1/20 exact formulations. Part of the gain is therefore format; the rest is formulation.

**Main failure: mixing problems, 0/40 on the synthetic test.** Coefficients are right, but minimum requirements (`>=`) are written as caps (`<=`). A teacher-forcing probe (`src/lp_llm/probe.py`) shows that everything hinges on the sense of the first constraint; later constraints copy it with probability ≥ 0.99. Two causes:

1. Under-learning: after 19 steps, P(`>=`) at that position is only 0.54 on the training examples themselves (0.001 for the base model). The mean loss (0.029) hides it, since one token weighs about 1 % of an example's loss.
2. Decoding bias: the `repetition_penalty=1.1` inherited from the model's generation config also penalises prompt tokens. The instruction contains the token ` ">` but not ` "<`, so only `>=` is penalised. The argmax becomes `<=` in 30/30 validation cases.

The penalised probe predicts the generated first sense in 78/78 readable synthetic outputs.

## Method

- **Data.** 16 human-reviewed templates, assigned to train / validation / test by lineage *before* sampling (8 / 4 / 4), giving 300 / 60 / 80 examples. Seeded generation, HiGHS-based admission (feasible, bounded, numerically clean), no duplicate text or normalised formulation across splits, SHA-256 hashes in `data/corpus_v1_manifest.json`. The synthetic test is balanced between optima on an axis and optima with both variables positive.
- **Independent set.** `data/human_test.jsonl`: 20 statements written outside the templates by an AI assistant (Codex), with references checked against a second transcription, HiGHS and an exact rational vertex enumeration. Eight mix caps and minimums; "linear" is absent from three. Never used for training or checkpoint selection.
- **Training.** Plain PyTorch loop with Transformers and PEFT, BF16, gradient checkpointing, lr 1e-4, effective batch 16. The loss covers only the target JSON and the end token; prompt and padding get label `-100`. The mask was verified by decoding the supervised tokens of all 360 training and validation examples.
- **Evaluator** (`src/lp_llm/verify.py`), four independent levels:
  1. JSON conforming to the schema;
  2. exact formulation after normalisation (constraint order, `>=` → `<=`, common positive factors);
  3. the predicted problem is solved;
  4. the predicted solution is feasible and optimal **on the reference problem**, with relative tolerances. Solution vectors are not compared, since optima can be multiple.

  Level 4 can succeed while level 2 fails: three independent cases reach the reference optimum despite an omitted constraint.

## Limitations

- Toy scale: 2 variables, 2–3 constraints, 300 training examples, one seed. With 20 independent cases, a difference of a few cases is not significant.
- In corpus v1, each family uses a single inequality sense. The adapter learned that correlation, which hurts statements mixing caps and minimums (1/8).
- The synthetic test ran in batches of 8 with left padding, the independent set one case at a time. On 8 control cases the scores match, but 2 of 8 texts differ.
- The diagnostic was made after reading test outputs. A v2 re-evaluated on these tests would be an iteration, not a blind measurement.

## Next iteration (planned, not run)

Protocol fixed before execution in the diagnostic report: E1, decoding without repetition penalty, measured on validation; E2, three epochs with one checkpoint per epoch, selection on validation exact formulation, then a single final evaluation on the tests.

## Reproduce

PowerShell, from the repository root, with the dependencies of `requirements.txt` installed:

```powershell
$env:PYTHONPATH = 'src'
python -m lp_llm.corpus --output runs/corpus_v1_reproduction   # regenerate the splits
python -m lp_llm.train --check-only                             # check hashes and loss mask
python -m lp_llm.train                                          # one epoch, BF16, CUDA
python -m lp_llm.evaluate                                       # base model, independent set
python -m lp_llm.evaluate --adapter runs/lora_v1 --output runs/lora_independent_v1.json
python -m lp_llm.evaluate --dataset data/test.jsonl --batch-size 8 --adapter runs/lora_v1 --output runs/lora_synthetic_reproduction.json
python -m pytest -q -p no:cacheprovider                         # 90 passed, 1 xfailed
```

Configuration in `configs/sft_lora.json`. Raw predictions, training log and probe output are versioned in `runs/`; adapter weights (17 MB) are not. Versions recorded for the v1 run: torch 2.8.0+cu128, transformers 5.22.1, peft 0.21.2, Windows 11, RTX 4060.

## Layout

```text
src/lp_llm/   schema, solver (JSON -> linprog), generate/corpus, train, evaluate, verify, probe
data/         train / validation / test / human_test (.jsonl) and corpus manifest
templates/    reviewed templates
reports/      results, diagnostic, learning notes (French)
runs/         predictions, training log, probe output
tests/        schema, solver, generator, corpus and verifier tests
```
