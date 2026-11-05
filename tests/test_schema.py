import copy
import json

import pytest

from lp_llm.schema import SCHEMA, get_valid_json, is_number, respect_problem_perimeter

# Exemple atelier : sert de base valide. Chaque cas invalide n'en modifie qu'un champ,
# pour qu'un contrôle ne puisse pas en masquer un autre.
BASE = {
    "variables": ["x1", "x2"],
    "objective": {"sense": "max", "coefficients": [30, 40]},
    "constraints": [
        {"coefficients": [2, 1], "sense": "<=", "rhs": 100},
        {"coefficients": [1, 2], "sense": "<=", "rhs": 80},
    ],
    "bounds": [[0, None], [0, None]],
}


def variant(modify):
    """Copie de BASE modifiée par `modify`, sérialisée en JSON."""
    d = copy.deepcopy(BASE)
    modify(d)
    return json.dumps(d)


def set_constraint(i, **fields):
    return lambda d: d["constraints"][i].update(fields)


# (nom, json, fragment du message attendu ; None = valide)
CASES = [
    ("valide", json.dumps(BASE), None),
    ("objective vide", variant(lambda d: d.update(objective={})), "'coefficients'"),
    ("objective sans sense", variant(lambda d: d["objective"].pop("sense")), "'sense'"),
    ("objective: sense inconnu", variant(lambda d: d["objective"].update(sense="maximize")), "Objective sense"),
    ("objective: coefficients non liste", variant(lambda d: d["objective"].update(coefficients=5)), "Coefficients in objective is not a list"),
    ("objective: 3 coefficients", variant(lambda d: d["objective"].update(coefficients=[1, 2, 3])), "Number of coefficients in objective"),
    ("objective: coefficient null", variant(lambda d: d["objective"].update(coefficients=[30, None])), "Coefficients in objective are not all numbers"),
    ("variables: noms inversés", variant(lambda d: d.update(variables=["x2", "x1"])), "Variables are not named"),
    ("variables: 3 variables", variant(lambda d: d.update(variables=["x1", "x2", "x3"])), "Number of variables"),
    ("contraintes: 1 seule", variant(lambda d: d["constraints"].pop()), "less than 2"),
    ("contraintes: 4", variant(lambda d: d["constraints"].extend(copy.deepcopy(d["constraints"]))), "greater than 3"),
    ("contraintes: éléments non dict", variant(lambda d: d.update(constraints=[5, 5])), "Constraint is not a dictionary"),
    ("contrainte: sense inconnu", variant(set_constraint(0, sense="<")), "Constraint sense"),
    ("contrainte: sans rhs", variant(lambda d: d["constraints"][0].pop("rhs")), "'rhs'"),
    ("contrainte: coefficients non liste", variant(set_constraint(0, coefficients=5)), "Coefficients in constraint is not a list"),
    ("contrainte: 3 coefficients", variant(set_constraint(0, coefficients=[1, 2, 3])), "Number of coefficients in constraint"),
    ("contrainte: coefficient inf", variant(set_constraint(0, coefficients=[2, float("inf")])), "Coefficients in constraint are not all numbers"),
    ("contrainte: coefficient null", variant(set_constraint(0, coefficients=[2, None])), "Coefficients in constraint are not all numbers"),
    ("contrainte: rhs booléen", variant(set_constraint(0, rhs=True)), "rhs is not a number"),
    ("contrainte: rhs NaN", variant(set_constraint(0, rhs=float("nan"))), "rhs is not a number"),
    ("contrainte: rhs chaîne", variant(set_constraint(0, rhs="100")), "rhs is not a number"),
    ("bounds: pas une liste de listes", variant(lambda d: d.update(bounds=[1, 2])), "Bound is not a list"),
    ("bounds: 1 seule borne", variant(lambda d: d.update(bounds=[[0, None]])), "Number of bounds"),
    ("bounds: 3 éléments", variant(lambda d: d.update(bounds=[[0, None, 1], [0, None]])), "exactly two elements"),
    ("bounds: inférieure null", variant(lambda d: d.update(bounds=[[None, 12], [0, None]])), "Lower bound"),
    ("bounds: inférieure négative", variant(lambda d: d.update(bounds=[[-1, None], [0, None]])), "non-negative"),
    ("bounds: inférieure > supérieure", variant(lambda d: d.update(bounds=[[5, 1], [0, None]])), "greater than upper"),
    ("bounds: supérieure négative", variant(lambda d: d.update(bounds=[[0, -1], [0, None]])), "greater than upper"),
    ("bounds: inférieure positive valide", variant(lambda d: d.update(bounds=[[2, None], [0, None]])), None),
    ("bounds: inférieure 0.0 et supérieure finie valides", variant(lambda d: d.update(bounds=[[0.0, 50], [3, 7]])), None),
    ("bounds: inférieure = supérieure valide", variant(lambda d: d.update(bounds=[[4, 4], [0, None]])), None),
    ("bounds: supérieure inf", variant(lambda d: d.update(bounds=[[0, float("inf")], [0, None]])), "Upper bound is not a number"),
    ("champ manquant: bounds", variant(lambda d: d.pop("bounds")), "'bounds'"),
    ("champ en trop: racine", variant(lambda d: d.update(explanation="texte")), "Unexpected keys at top level"),
    ("champ en trop: objective", variant(lambda d: d["objective"].update(comment="profit")), "Unexpected keys in objective"),
    ("champ en trop: contrainte", variant(set_constraint(1, name="c2")), "Unexpected keys in constraint"),
]


@pytest.mark.parametrize("name, json_string, expected", CASES, ids=[c[0] for c in CASES])
def test_respect_problem_perimeter(name, json_string, expected):
    ok, data = get_valid_json(json_string)
    assert ok, f"le JSON du cas '{name}' doit être parsable : {data}"
    is_valid, message = respect_problem_perimeter(data, SCHEMA)
    if expected is None:
        assert is_valid, message
    else:
        assert not is_valid
        assert expected in message


@pytest.mark.parametrize(
    "raw",
    ["", "{", "pas du json", "[" * 100000, None, 5],
    ids=["vide", "tronqué", "texte", "imbrication profonde", "None", "entier"],
)
def test_invalid_json_is_rejected_without_exception(raw):
    ok, _ = get_valid_json(raw)
    assert not ok


@pytest.mark.parametrize("raw", ["[]", "5", "null", '"x"'], ids=["liste", "entier", "null", "chaîne"])
def test_json_not_an_object(raw):
    ok, data = get_valid_json(raw)
    assert ok
    is_valid, _ = respect_problem_perimeter(data, SCHEMA)
    assert not is_valid


def test_1e999_is_rejected():
    # 1e999 est lu comme inf par Python
    raw = json.dumps(BASE).replace("[2, 1]", "[2, 1e999]", 1)
    ok, data = get_valid_json(raw)
    assert ok
    is_valid, _ = respect_problem_perimeter(data, SCHEMA)
    assert not is_valid


@pytest.mark.parametrize("value", [0, 3, -2, 2.5, 1e300, 10**400])
def test_is_number_accepts(value):
    assert is_number(value)


@pytest.mark.parametrize(
    "value", [True, False, None, "3", [], {}, float("nan"), float("inf"), float("-inf")]
)
def test_is_number_rejects(value):
    assert not is_number(value)
