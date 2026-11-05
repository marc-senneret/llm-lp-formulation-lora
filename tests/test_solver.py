import json

import pytest

from lp_llm.solver import solve_lp_problem


def test_workshop_example():
    # Exemple atelier : max 30*x1 + 40*x2 sous 2*x1 + x2 <= 100 et x1 + 2*x2 <= 80.
    # Calcul à la main : les deux contraintes sont saturées en l'optimum,
    # donc 2*x1 + x2 = 100 et x1 + 2*x2 = 80 => x1 = 40, x2 = 20, objectif = 30*40 + 40*20 = 2000.
    problem = {
        "variables": ["x1", "x2"],
        "objective": {"sense": "max", "coefficients": [30, 40]},
        "constraints": [
            {"coefficients": [2, 1], "sense": "<=", "rhs": 100},
            {"coefficients": [1, 2], "sense": "<=", "rhs": 80},
        ],
        "bounds": [[0, None], [0, None]],
    }
    result = solve_lp_problem(json.dumps(problem))

    assert result["status"] == "optimal"
    assert result["solution"] == pytest.approx([40, 20])
    assert result["objective_value"] == pytest.approx(2000)


def solve(sense, coefficients, constraints, bounds=None):
    """Construit le JSON d'un problème à 2 variables et le résout.

    constraints : liste de (coefficients, sense, rhs).
    """
    problem = {
        "variables": ["x1", "x2"],
        "objective": {"sense": sense, "coefficients": coefficients},
        "constraints": [{"coefficients": a, "sense": s, "rhs": r} for a, s, r in constraints],
        "bounds": bounds if bounds is not None else [[0, None], [0, None]],
    }
    return solve_lp_problem(json.dumps(problem))


def test_greater_equal_constraint():
    # max x1 + 2*x2 sous x1 + x2 <= 10, x1 >= 4, x2 <= 9.
    # Sur x1 + x2 = 10, l'objectif vaut 20 - x1 : il est maximal quand x1 est minimal,
    # donc x1 = 4 (la contrainte >= est saturée), x2 = 6, objectif = 4 + 12 = 16.
    # Si le >= était converti à l'envers (x1 <= 4), l'optimum serait x1 = 0, x2 = 9, objectif 18.
    result = solve("max", [1, 2], [([1, 1], "<=", 10), ([1, 0], ">=", 4), ([0, 1], "<=", 9)])

    assert result["status"] == "optimal"
    assert result["solution"] == pytest.approx([4, 6])
    assert result["objective_value"] == pytest.approx(16)


def test_minimization():
    # min 2*x1 + 3*x2 sous x1 + x2 >= 10 et x2 >= 1.
    # x1 coûte moins cher que x2 : on prend le minimum de x2 (= 1), donc x1 = 9,
    # objectif = 18 + 3 = 21. Si la minimisation était traitée comme une maximisation,
    # le problème serait non borné.
    result = solve("min", [2, 3], [([1, 1], ">=", 10), ([0, 1], ">=", 1)])

    assert result["status"] == "optimal"
    assert result["solution"] == pytest.approx([9, 1])
    assert result["objective_value"] == pytest.approx(21)


def test_lower_bound_on_first_variable():
    # min 2*x1 + x2 sous x1 + x2 >= 1 et x2 <= 5, avec x1 dans [1, +inf[.
    # Sans la borne, l'optimum serait x1 = 0, x2 = 1 (objectif 1).
    # Avec x1 >= 1 : x1 = 1, x2 = 0, objectif = 2.
    result = solve(
        "min", [2, 1], [([1, 1], ">=", 1), ([0, 1], "<=", 5)], bounds=[[1, None], [0, None]]
    )

    assert result["status"] == "optimal"
    assert result["solution"] == pytest.approx([1, 0])
    assert result["objective_value"] == pytest.approx(2)


def test_upper_bound_on_second_variable():
    # max 2*x1 + 3*x2 sous x1 + x2 <= 10 et x1 <= 4, avec x2 dans [0, 1].
    # Sans la borne, l'optimum serait x1 = 0, x2 = 10 (objectif 30).
    # Avec x2 <= 1 : x1 = 4, x2 = 1, objectif = 8 + 3 = 11.
    result = solve(
        "max", [2, 3], [([1, 1], "<=", 10), ([1, 0], "<=", 4)], bounds=[[0, None], [0, 1]]
    )

    assert result["status"] == "optimal"
    assert result["solution"] == pytest.approx([4, 1])
    assert result["objective_value"] == pytest.approx(11)


def test_infeasible_problem():
    # x1 + x2 <= 5 et x1 + x2 >= 10 : l'intersection des contraintes est vide.
    result = solve("max", [1, 1], [([1, 1], "<=", 5), ([1, 1], ">=", 10)])

    assert result["status"] == "infeasible"
    assert "solution" not in result


@pytest.mark.xfail(strict=True, reason="Test volontairement faux : vérifie que pytest détecte un écart")
def test_wrong_expected_value_must_fail():
    # L'optimum de l'exemple atelier est 2000, pas 1800.
    # strict=True : si ce test passait, la suite passerait au rouge.
    result = solve("max", [30, 40], [([2, 1], "<=", 100), ([1, 2], "<=", 80)])

    assert result["objective_value"] == pytest.approx(1800)
