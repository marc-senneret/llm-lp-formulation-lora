from copy import deepcopy
import json
from pathlib import Path

import pytest

from lp_llm.corpus import formulation_key, generate_splits, validate_templates


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


@pytest.fixture
def candidates():
    return load("templates/corpus_v1_candidates.json")


def test_candidates_require_approval_for_final_corpus(candidates):
    validate_templates(candidates, preview=True)
    with pytest.raises(ValueError, match="not approved"):
        validate_templates(candidates, preview=False)


def test_lineage_cannot_cross_splits(candidates):
    train = next(row for row in candidates if row["split"] == "train")
    validation = next(row for row in candidates if row["split"] == "validation")
    validation["lineage_id"] = train["lineage_id"]
    with pytest.raises(ValueError, match="lineage assigned"):
        validate_templates(candidates, preview=True)


def test_missing_numeric_field_cannot_be_rendered(candidates):
    candidates[0]["text"] = candidates[0]["text"].replace("{rhs_1}", "")
    with pytest.raises(ValueError, match="invalid statement fields"):
        validate_templates(candidates, preview=True)


def test_corpus_key_for_reordered_scaled_inequalities():
    ref = json.loads(Path("data/human_test.jsonl").read_text(encoding="utf-8").splitlines()[0])["reference"]
    scaled = deepcopy(ref)
    scaled["objective"]["coefficients"] = [2*x for x in ref["objective"]["coefficients"]]
    scaled["constraints"].reverse()
    for row in scaled["constraints"]:
        row.update(coefficients=[-3*x for x in row["coefficients"]], sense=">=", rhs=-3*row["rhs"])
    assert formulation_key(ref) == formulation_key(scaled)
    scaled["constraints"][0]["rhs"] += 1
    assert formulation_key(ref) != formulation_key(scaled)


def test_attempt_limit_reports_the_group_and_seed(candidates, monkeypatch):
    config = load("configs/generate_v1.json")
    profile = load("configs/corpus_v1.json")
    config["generation"]["max_attempts_per_example"] = 1
    monkeypatch.setattr("lp_llm.corpus.solve_lp_problem", lambda raw: {"status": "infeasible"})
    with pytest.raises(ValueError, match=r"train/production/2 example 1: .*1000.*solver_infeasible"):
        generate_splits(config, profile, candidates, [])
