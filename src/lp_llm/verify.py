"""Compare a raw LP response to a trusted, independently checked reference."""

from collections import Counter
from fractions import Fraction
import json
import math

from lp_llm.schema import SCHEMA, get_valid_json, respect_problem_perimeter
from lp_llm.solver import solve_lp_problem


def constraint_key(row: dict) -> tuple:
    # Decimal spellings such as 0.1 represent exact decimal numbers here.
    values = tuple(Fraction(str(x)) for x in (*row["coefficients"], row["rhs"]))
    if row["sense"] == ">=":
        values = tuple(-x for x in values)
    first = next((x for x in values if x), Fraction(1))
    scale = first if row["sense"] == "=" else abs(first)
    return row["sense"] == "=", tuple(x / scale for x in values)


def _reference_success(solution: list, reference: dict, optimum: float) -> bool:
    for x, (lower, upper) in zip(solution, reference["bounds"]):
        if x < lower - 1e-6 * (1 + abs(lower)):
            return False
        if upper is not None and x > upper + 1e-6 * (1 + abs(upper)):
            return False
    for row in reference["constraints"]:
        residual = math.fsum(a * x for a, x in zip(row["coefficients"], solution)) - row["rhs"]
        tolerance = 1e-6 * (1 + abs(row["rhs"]))
        if row["sense"] in ("<=", "=") and residual > tolerance:
            return False
        if row["sense"] in (">=", "=") and residual < -tolerance:
            return False
    value = math.fsum(a * x for a, x in zip(reference["objective"]["coefficients"], solution))
    return abs(value - optimum) <= 1e-5 * (1 + abs(optimum))


def verify_lp(raw: str, reference: dict) -> dict:
    """Score format, formulation, predicted solve and success on the reference."""
    issues = []
    checks = dict(format=False, formulation=False, solve=False, reference=False, issues=issues)
    ok, predicted = get_valid_json(raw)
    if not ok:
        issues.append(f"JSON — {predicted}")
        return checks
    ok, message = respect_problem_perimeter(predicted, SCHEMA)
    if not ok:
        issues.append(f"Schéma — {message}")
        return checks
    checks["format"] = True

    if predicted["objective"] != reference["objective"]:
        issues.append("Formulation — objectif différent.")
    if predicted["bounds"] != reference["bounds"]:
        issues.append("Formulation — bornes différentes.")
    if (Counter(map(constraint_key, predicted["constraints"]))
            != Counter(map(constraint_key, reference["constraints"]))):
        issues.append("Formulation — une ou plusieurs contraintes diffèrent.")
    checks["formulation"] = not issues

    try:
        result = solve_lp_problem(raw)
    except (ValueError, OverflowError) as error:
        issues.append(f"Résolution — {error}")
        return checks
    if result["status"] != "optimal" or not all(math.isfinite(x) for x in (
            *result["solution"], result["objective_value"])):
        issues.append(f"Résolution — {result['status']} ({result['message']}).")
        return checks
    checks["solve"] = True

    expected = solve_lp_problem(json.dumps(reference, allow_nan=False))
    if expected["status"] != "optimal" or not math.isfinite(expected["objective_value"]):
        raise ValueError("La référence doit avoir un optimum fini.")
    checks["reference"] = _reference_success(result["solution"], reference, expected["objective_value"])
    if not checks["reference"]:
        issues.append("Référence — la solution prédite n'est pas faisable ou optimale sur la référence.")
    return checks
