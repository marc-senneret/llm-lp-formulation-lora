import copy
import json
from pathlib import Path
import random

import pytest

from lp_llm import generate


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs/generate_v1.json").read_text(encoding="utf-8"))
TEMPLATES = json.loads((ROOT / "templates/candidates.json").read_text(encoding="utf-8"))
PILOT_CONFIG = json.loads((ROOT / "configs/pilot_v2.json").read_text(encoding="utf-8"))
PILOT_REVIEWS = json.loads((ROOT / "reviews/pilot_v2.json").read_text(encoding="utf-8"))


def test_pilot_reproducible_and_independent_of_global_random():
    state = random.getstate()
    first = generate.generate_pilot(CONFIG, TEMPLATES, PILOT_CONFIG)
    assert random.getstate() == state
    assert generate.generate_pilot(CONFIG, TEMPLATES, PILOT_CONFIG) == first
    assert len(first["examples"]) == 10
    assert [e["family"] for e in first["examples"]] == ["production"] * 5 + ["mixing"] * 5
    assert all(e["split"] == "development" and e["human_review"] == "pending"
               for e in first["examples"])
    seeds = [a["seed"] for a in first["attempts"]]
    assert seeds == list(range(CONFIG["master_seed"], CONFIG["master_seed"] + len(seeds)))
    assert any(a["diagnostic"]["reason"] == "target_geometry_not_met" for a in first["attempts"])
    for family in ("production", "mixing"):
        examples = [e for e in first["examples"] if e["family"] == family]
        assert [e["stratum"] for e in examples] == ["interior_two_active"] * 3 + ["unrestricted"] * 2
        assert [e["diagnostic"]["geometry_matches_target"] for e in examples] == [True] * 3 + [None] * 2
        for example in examples[:3]:
            solution = example["solver_result"]["solution"]
            assert min(solution) > PILOT_CONFIG["positive_variable_tolerance"]
            for row in example["reference"]["constraints"]:
                lhs = sum(a * x for a, x in zip(row["coefficients"], solution))
                assert lhs == pytest.approx(row["rhs"], rel=1e-6, abs=1e-6)


def test_reviewed_pilot_preserves_rational_results_and_review_scope():
    pilot = generate.generate_pilot(CONFIG, TEMPLATES, PILOT_CONFIG)
    examples = {example["id"]: example for example in pilot["examples"]}
    assert pilot["summary"]["interior_two_active"] == 6
    assert all(example["exact_result"] is not None for example in examples.values())
    example = examples["pilot_production_003"]
    assert example["diagnostic"]["constraint_slacks"] == [0.0, 0.0]
    assert example["exact_result"] == {
        "solution": ["189/11", "112/11"],
        "objective_value": "12432/11",
        "constraint_slacks": ["0", "0"],
    }
    assert examples["pilot_mixing_005"]["exact_result"]["constraint_slacks"] == ["1270/3", "0"]
    generate.apply_pilot_reviews(pilot, PILOT_REVIEWS)
    assert all(example["human_review"] == "reviewed" for example in examples.values())
    changed = dict(example, statement=example["statement"] + " Edit.", human_review="pending")
    generate.apply_pilot_reviews({"examples": [changed]}, PILOT_REVIEWS)
    assert changed["human_review"] == "pending"


def test_multiple_optima_and_inactive_constraint_are_allowed():
    # Min x1+x2 with x1+x2>=10 and x1+x2>=5: whole optimal segment.
    reference = {
        "constraints": [
            {"coefficients": [1, 1], "sense": ">=", "rhs": 10},
            {"coefficients": [1, 1], "sense": ">=", "rhs": 5},
        ]
    }
    result = {"status": "optimal", "solution": [4, 6], "objective_value": 10}
    diagnostic = generate.check_admission(reference, result, CONFIG["admission"])
    assert diagnostic["accepted"]
    assert diagnostic["active_constraint_indices"] == [0]
    assert diagnostic["constraint_slacks"] == [0, 5]


@pytest.mark.parametrize("solution, objective, reason", [
    ([0, 0], 0, "origin_solution"),
    ([float("nan"), 0], 10, "nonfinite_or_missing_result"),
    ([4, 6], float("inf"), "nonfinite_or_missing_result"),
    ([4, 5], 9, "constraint_violation"),
    ([6, 6], 12, "no_active_constraint"),
])
def test_bad_solver_result_is_rejected(solution, objective, reason):
    reference = {"constraints": [
        {"coefficients": [1, 1], "sense": ">=", "rhs": 10},
        {"coefficients": [1, 1], "sense": ">=", "rhs": 5},
    ]}
    result = {"status": "optimal", "solution": solution, "objective_value": objective}
    assert generate.check_admission(reference, result, CONFIG["admission"])["reason"] == reason


def test_attempt_limit_is_bounded_and_diagnosed(monkeypatch):
    config = copy.deepcopy(CONFIG)
    config["generation"]["max_attempts_per_example"] = 3
    calls = []

    def reject(reference_json):
        calls.append(json.loads(reference_json))
        return {"status": "infeasible"}

    monkeypatch.setattr(generate, "solve_lp_problem", reject)
    with pytest.raises(generate.AttemptLimitError, match="last_seed=44.*solver_infeasible.*3") as error:
        generate.generate_pilot(config, TEMPLATES, PILOT_CONFIG)
    assert len(calls) == 3
    assert [attempt["seed"] for attempt in error.value.attempts] == [42, 43, 44]


def test_missing_numeric_role_is_not_silently_rendered():
    template = copy.deepcopy(TEMPLATES[0])
    template["text"] = template["text"].replace("{rhs_1}", "100")
    reference = generate.sample_reference("production", 2, 42, CONFIG)
    with pytest.raises(ValueError, match="required numeric fields"):
        generate.render_statement(template, reference)


def test_geometry_filter_has_its_own_limit_and_unrestricted_cases_still_allow_axes(monkeypatch):
    config = copy.deepcopy(CONFIG)
    config["generation"]["max_attempts_per_example"] = 2

    def reference_on_axis(family, constraint_count, seed, config):
        sense = "<=" if family == "production" else ">="
        return {"constraints": [
            {"coefficients": [1, 1], "sense": sense, "rhs": 10},
            {"coefficients": [1, 1], "sense": sense, "rhs": 20 if family == "production" else 5},
        ], "objective": {"coefficients": [1, 1]}}

    monkeypatch.setattr(generate, "sample_reference", reference_on_axis)
    monkeypatch.setattr(generate, "solve_lp_problem", lambda _: {
        "status": "optimal", "solution": [10, 0], "objective_value": 10})
    profile = dict(PILOT_CONFIG, per_family=1, targeted_per_family=1)
    with pytest.raises(generate.AttemptLimitError) as error:
        generate.generate_pilot(config, TEMPLATES, profile)
    assert len(error.value.attempts) == 2
    assert all(a["diagnostic"]["reason"] == "target_geometry_not_met"
               and a["diagnostic"]["numeric_admission_accepted"]
               and a["diagnostic"]["geometry_matches_target"] is False for a in error.value.attempts)

    profile["targeted_per_family"] = 0
    pilot = generate.generate_pilot(config, TEMPLATES, profile)
    assert len(pilot["examples"]) == 2
    assert all(e["stratum"] == "unrestricted" for e in pilot["examples"])


def test_wrong_loose_rhs_can_keep_the_same_optimum():
    # Both references remain valid 2-row LPs: a numeric success cannot detect this error.
    reference = {
        "variables": ["x1", "x2"],
        "objective": {"sense": "min", "coefficients": [1, 2]},
        "constraints": [
            {"coefficients": [1, 1], "sense": ">=", "rhs": 10},
            {"coefficients": [1, 1], "sense": ">=", "rhs": 5},
        ],
        "bounds": [[0, None], [0, None]],
    }
    wrong = copy.deepcopy(reference)
    wrong["constraints"][1]["rhs"] = 4
    original_result = generate.solve_lp_problem(json.dumps(reference))
    wrong_result = generate.solve_lp_problem(json.dumps(wrong))
    assert reference != wrong
    assert original_result["status"] == wrong_result["status"] == "optimal"
    assert original_result["objective_value"] == wrong_result["objective_value"] == 10
    assert original_result["solution"] == wrong_result["solution"] == [10, 0]
