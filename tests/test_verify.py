import copy
import json

from lp_llm.verify import verify_lp


REFERENCE = {
    "variables": ["x1", "x2"],
    "objective": {"sense": "min", "coefficients": [1, 2]},
    "constraints": [
        {"coefficients": [1, 1], "sense": ">=", "rhs": 10},
        {"coefficients": [1, 1], "sense": ">=", "rhs": 5},
    ],
    "bounds": [[0, None], [0, None]],
}


def test_wrong_loose_rhs_preserves_reference_success_but_not_formulation():
    prediction = copy.deepcopy(REFERENCE)
    prediction["constraints"][1]["rhs"] = 4
    checks = verify_lp(json.dumps(prediction), REFERENCE)
    assert checks["format"] and checks["solve"] and checks["reference"]
    assert not checks["formulation"]


def test_equivalent_constraints_can_change_order_scale_and_direction():
    prediction = dict(REFERENCE, constraints=[
        {"coefficients": [-2, -2], "sense": "<=", "rhs": -10},
        {"coefficients": [3, 3], "sense": ">=", "rhs": 30},
    ])
    assert verify_lp(json.dumps(prediction), REFERENCE)["issues"] == []


def test_valid_predicted_optimum_can_violate_reference():
    prediction = copy.deepcopy(REFERENCE)
    prediction["constraints"][0]["rhs"] = 9
    checks = verify_lp(json.dumps(prediction), REFERENCE)
    assert checks["solve"]
    assert not checks["reference"]


def test_different_optimal_points_pass_on_the_reference():
    reference = dict(REFERENCE, objective={"sense": "min", "coefficients": [1, 1]})
    for coefficients in ([1, 2], [2, 1]):
        prediction = dict(reference, objective={"sense": "min", "coefficients": coefficients})
        assert verify_lp(json.dumps(prediction), reference)["reference"]


def test_duplicates_and_oversized_integers_get_diagnostics():
    raw = json.dumps(REFERENCE).replace('"sense": "min"', '"sense": "max", "sense": "min"', 1)
    checks = verify_lp(raw, REFERENCE)
    assert not checks["format"]
    assert "Duplicate key" in checks["issues"][0]
    prediction = dict(REFERENCE, objective={"sense": "min", "coefficients": [10**320, 2]})
    checks = verify_lp(json.dumps(prediction), REFERENCE)
    assert checks["format"] and not checks["solve"]
    assert any(issue.startswith("Résolution") for issue in checks["issues"])
