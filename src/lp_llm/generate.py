"""Small development pilot; this does not generate train/validation/test splits."""

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import random
from string import Formatter

from lp_llm.solver import solve_lp_problem


class AttemptLimitError(RuntimeError):
    """Keep attempted references available to the CLI when generation stops."""

    def __init__(self, message: str, attempts: list):
        super().__init__(message)
        self.attempts = attempts


def sample_reference(family: str, constraint_count: int, seed: int, config: dict) -> dict:
    """Use one local RNG per attempted instance, never the global generator."""
    senses = {"production": ("max", "<="), "mixing": ("min", ">=")}
    if family not in senses or constraint_count not in (2, 3):
        raise ValueError("Expected production/mixing and two or three constraints")
    sampling = config["numeric_sampling"]
    if (sampling["distribution"] != "uniform_integer"
            or not sampling["inclusive_bounds"] or not sampling["independent_draws"]):
        raise ValueError("Only independent uniform inclusive integer draws are supported")
    rng = random.Random(seed)

    def draw(name):
        interval = sampling[name]
        return rng.randint(interval["min"], interval["max"])

    objective_sense, constraint_sense = senses[family]
    return {
        "variables": ["x1", "x2"],
        "objective": {
            "sense": objective_sense,
            "coefficients": [draw("objective_coefficients") for _ in range(2)],
        },
        "constraints": [
            {"coefficients": [draw("constraint_coefficients") for _ in range(2)],
             "sense": constraint_sense, "rhs": draw("rhs")}
            for _ in range(constraint_count)
        ],
        "bounds": [[0, None], [0, None]],
    }


def check_admission(reference: dict, result: dict, rules: dict) -> dict:
    """Check the solver result on the original reference, including >= rows."""
    if result["status"] != rules["required_solver_status"]:
        return {"accepted": False, "reason": "solver_" + result["status"]}
    solution = result.get("solution", [])
    objective = result.get("objective_value")
    if (len(solution) != 2 or not all(math.isfinite(x) for x in solution)
            or objective is None or not math.isfinite(objective)):
        return {"accepted": False, "reason": "nonfinite_or_missing_result"}
    if max(abs(x) for x in solution) <= rules["origin_tolerance"]:
        return {"accepted": False, "reason": "origin_solution"}

    feasibility = rules["feasibility_tolerance"]
    bound_tolerance = feasibility["absolute"]
    if any(x < -bound_tolerance for x in solution):
        return {"accepted": False, "reason": "negative_solution"}
    active = []
    slacks = []
    activity = rules["active_constraint_tolerance"]
    for i, row in enumerate(reference["constraints"]):
        if not all(value > 0 for value in row["coefficients"]):
            return {"accepted": False, "reason": "nonpositive_constraint_coefficient"}
        lhs = sum(a * x for a, x in zip(row["coefficients"], solution))
        rhs = row["rhs"]
        if row["sense"] not in ("<=", ">="):
            return {"accepted": False, "reason": "unsupported_constraint_sense"}
        slack = rhs - lhs if row["sense"] == "<=" else lhs - rhs
        slacks.append(slack)
        if slack < -(feasibility["absolute"] + feasibility["relative"] * abs(rhs)):
            return {"accepted": False, "reason": "constraint_violation", "constraint_index": i}
        if abs(lhs - rhs) <= activity["absolute"] + activity["relative"] * abs(rhs):
            active.append(i)
    if rules["require_active_constraint"] and not active:
        return {"accepted": False, "reason": "no_active_constraint"}
    return {"accepted": True, "reason": "accepted", "active_constraint_indices": active,
            "constraint_slacks": slacks}


def render_statement(template: dict, reference: dict) -> str:
    """Only fill numeric fields; context and units belong to the fixed text."""
    if template["constraint_count"] != len(reference["constraints"]):
        raise ValueError("Template and reference constraint counts differ")
    values = dict(zip(("objective_x1", "objective_x2"), reference["objective"]["coefficients"]))
    for i, row in enumerate(reference["constraints"], 1):
        values.update({f"constraint_{i}_x1": row["coefficients"][0],
                       f"constraint_{i}_x2": row["coefficients"][1], f"rhs_{i}": row["rhs"]})
    fields = {field for _, field, _, _ in Formatter().parse(template["text"]) if field is not None}
    if fields != set(values):
        raise ValueError("Template must contain exactly the required numeric fields")
    return template["text"].format(**values)


def generate_pilot(config: dict, templates: list, pilot_config: dict) -> dict:
    """Visit production then mixing; advance the seed after every attempt."""
    per_family = pilot_config["per_family"]
    targeted = pilot_config["targeted_per_family"]
    positive_tolerance = pilot_config["positive_variable_tolerance"]
    if per_family < 1:
        raise ValueError("per_family must be positive")
    if not 0 <= targeted <= per_family:
        raise ValueError("targeted_per_family must be between zero and per_family")
    if not math.isfinite(positive_tolerance) or positive_tolerance <= 0:
        raise ValueError("positive_variable_tolerance must be finite and positive")
    maximum = config["generation"]["max_attempts_per_example"]
    if maximum < 1 or config["generation"]["on_attempt_limit"] != "error":
        raise ValueError("Expected a positive attempt limit and error on exhaustion")
    seed = config["master_seed"]
    examples, attempts = [], []
    for family in ("production", "mixing"):
        # Development witnesses may be needs_review. Never use this for final splits.
        witnesses = [t for t in templates if t["family"] == family and t["constraint_count"] == 2]
        if len(witnesses) != 1 or witnesses[0]["status"] not in ("needs_review", "accepted"):
            raise ValueError(f"Expected one usable two-constraint witness for {family}")
        template = witnesses[0]
        for number in range(1, per_family + 1):
            stratum = "interior_two_active" if number <= targeted else "unrestricted"
            for _ in range(maximum):
                instance_seed = seed
                seed += 1
                reference = sample_reference(family, template["constraint_count"], instance_seed, config)
                # The solver validates the schema and expects a JSON string.
                result = solve_lp_problem(json.dumps(reference, allow_nan=False))
                diagnostic = check_admission(reference, result, config["admission"])
                diagnostic["numeric_admission_accepted"] = diagnostic["accepted"]
                if diagnostic["accepted"]:
                    matches_target = (min(result["solution"]) > positive_tolerance
                                      and len(diagnostic["active_constraint_indices"]) == 2)
                    diagnostic["geometry_matches_target"] = matches_target
                    if stratum == "interior_two_active" and not matches_target:
                        diagnostic.update(accepted=False, reason="target_geometry_not_met")
                attempts.append({"family": family, "seed": instance_seed, "reference": reference,
                                 "stratum": stratum, "solver_result": result, "diagnostic": diagnostic})
                if diagnostic["accepted"]:
                    examples.append({
                        "id": f"pilot_{family}_{number:03d}", "split": "development",
                        "stratum": stratum,
                        "family": family, "template_id": template["template_id"],
                        "lineage_id": template["lineage_id"], "seed": instance_seed,
                        "statement": render_statement(template, reference), "reference": reference,
                        "solver_result": result, "diagnostic": diagnostic,
                        "human_review": "pending",
                    })
                    break
            else:
                reasons = Counter(a["diagnostic"]["reason"] for a in attempts[-maximum:])
                raise AttemptLimitError(f"Attempt limit reached: {family} example {number}; "
                                        f"last_seed={seed - 1}; reasons={dict(reasons)}", attempts)
    summary = {
        "examples": len(examples), "attempts": len(attempts),
        "admission_rate": len(examples) / len(attempts),
        "numeric_admission_rate": sum(a["diagnostic"]["numeric_admission_accepted"]
                                      for a in attempts) / len(attempts),
        "selected_by_stratum": dict(Counter(e["stratum"] for e in examples)),
        "geometry_matches_target": sum(e["diagnostic"]["geometry_matches_target"] for e in examples),
        "rejections": dict(Counter(a["diagnostic"]["reason"] for a in attempts
                                   if not a["diagnostic"]["accepted"])),
        "seed_rule": "production_then_mixing_increment_after_every_attempt",
        "next_seed": seed,
    }
    return {"config": config, "pilot_config": pilot_config, "templates": templates, "summary": summary,
            "examples": examples, "attempts": attempts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/generate_v1.json"))
    parser.add_argument("--templates", type=Path, default=Path("templates/candidates.json"))
    parser.add_argument("--pilot-config", type=Path, default=Path("configs/pilot_v2.json"))
    parser.add_argument("--per-family", type=int, default=None)
    parser.add_argument("--output", type=Path, default=Path("runs/generation_pilot_v2"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    templates = json.loads(args.templates.read_text(encoding="utf-8"))
    pilot_config = json.loads(args.pilot_config.read_text(encoding="utf-8"))
    if args.per_family is not None:
        pilot_config["per_family"] = args.per_family
    try:
        pilot = generate_pilot(config, templates, pilot_config)
    except AttemptLimitError as error:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "failure.json").write_text(
            json.dumps({"error": str(error), "config": config, "pilot_config": pilot_config, "templates": templates,
                        "attempts": error.attempts}, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        raise
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "pilot.json").write_text(
        json.dumps(pilot, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    review = ["# Development pilot — human review pending", "",
              f"Pilot version: {pilot_config['pilot_version']}", "",
              "Not part of train/validation/test. Compare each statement with its reference.", ""]
    for example in pilot["examples"]:
        review += ["## " + example["id"], "", f"Seed: {example['seed']}", "",
                   f"Stratum: {example['stratum']}", "",
                   example["statement"], "", "```json",
                   json.dumps({key: example[key] for key in ("reference", "solver_result", "diagnostic")},
                              indent=2), "```", "", "Human review: pending.", ""]
    (args.output / "review.md").write_text("\n".join(review), encoding="utf-8")
    print(json.dumps(pilot["summary"], indent=2))


if __name__ == "__main__":
    main()
