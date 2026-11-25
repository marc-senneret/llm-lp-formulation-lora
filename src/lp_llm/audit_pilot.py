"""Write the issues report and the LaTeX review booklet for pilot v2."""

import argparse
import json
from pathlib import Path

from lp_llm.generate import review_fingerprint
from lp_llm.verify import verify_lp


REVIEW_DIR = Path("reviews/validation_pilote_v2")
CHECKS = {"format": "JSON et schéma", "formulation": "Formulation",
          "solve": "Résolution", "reference": "Succès sur la référence"}
TEX_ESCAPES = str.maketrans({
    "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$",
    "&": r"\&", "#": r"\#", "%": r"\%", "_": r"\_", "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
})


def _reference(record: dict) -> dict:
    sense, *objective = record["objective"]
    return {
        "variables": ["x1", "x2"], "bounds": record["bounds"],
        "objective": {"sense": sense, "coefficients": objective},
        "constraints": [{"coefficients": [a, b], "sense": sign, "rhs": rhs}
                        for a, b, sign, rhs in record["constraints"]],
    }


def _report(results: dict, observations: list, input_issues: list, marc_review: str) -> str:
    lines = [
        "# Contrôle du pilote v2", "",
        "## Contrôles automatiques", "",
        "Le JSON du pilote est comparé à une transcription des seuls énoncés. "
        "Le pilote fournit des objets JSON, qui sont sérialisés pour ce contrôle.", "",
        "Les contraintes sont comparées à l'ordre près et à un facteur positif près. "
        "Une inégalité peut être écrite dans l'autre sens en changeant les deux signes. "
        "L'objectif et les bornes sont comparés dans les unités de l'énoncé.", "",
        "| Vérification | Cas réussis |", "| --- | ---: |",
    ]
    for key, label in CHECKS.items():
        lines.append(f"| {label} | {sum(item[key] for item in results.values())}/{len(results)} |")
    lines += ["", "### Anomalies automatiques", ""]
    issues = list(input_issues)
    for identifier, item in results.items():
        issues.extend(f"`{identifier}` — {issue}" for issue in item["issues"])
    lines.extend(f"- {issue}" for issue in issues or ["Aucune anomalie détectée."])
    lines += ["", "## Relecture de l’assistant", ""]
    lines.extend(f"- {note}" for note in observations or ["Relecture en attente."])
    lines += ["", "## Validation de Marc", "", marc_review, ""]
    return "\n".join(lines)


def _linear_form(coefficients: list) -> str:
    terms = []
    for i, coefficient in enumerate(coefficients, 1):
        if coefficient:
            magnitude = "" if abs(coefficient) == 1 else str(abs(coefficient))
            sign = "-" if coefficient < 0 else "+" if terms else ""
            terms.append(rf"{sign}{magnitude}x_{i}")
    return " ".join(terms) or "0"


def _math_form(problem: dict) -> str:
    objective = problem["objective"]
    signs = {"<=": r"\le", ">=": r"\ge", "=": "="}
    lines = [rf"\{objective['sense']}_{{x_1,x_2\in\mathbb{{R}}}}\quad"
             rf"& {_linear_form(objective['coefficients'])} \\"]
    for i, row in enumerate(problem["constraints"]):
        label = r"\text{s.c.}" if i == 0 else ""
        lines.append(rf"{label}\quad & {_linear_form(row['coefficients'])}"
                     rf" {signs[row['sense']]} {row['rhs']} \\")
    for i, (lower, upper) in enumerate(problem["bounds"], 1):
        bound = rf"x_{i} \ge {lower}" if upper is None else rf"{lower} \le x_{i} \le {upper}"
        lines.append(rf"& {bound} \\")
    return "\n".join([r"\[\begin{aligned}", *lines, r"\end{aligned}\]"])


def _compact_json(problem: dict) -> str:
    rows = ",\n".join("    " + json.dumps(row) for row in problem["constraints"])
    return "\n".join([
        "{", f'  "variables": {json.dumps(problem["variables"])},',
        f'  "objective": {json.dumps(problem["objective"])},',
        '  "constraints": [', rows, "  ],",
        f'  "bounds": {json.dumps(problem["bounds"])}', "}",
    ])


def _booklet(examples: list) -> str:
    lines = [r"""\documentclass[11pt,a4paper]{article}
\usepackage[T1]{fontenc}
\usepackage[french]{babel}
\usepackage{amsmath,amssymb}
\usepackage[margin=23mm]{geometry}
\usepackage{xcolor}
\definecolor{heading}{HTML}{184154}
\setlength{\parindent}{0pt}
\setlength{\parskip}{5pt}
\newcommand{\rubrique}[1]{\par\medskip{\large\bfseries\color{heading}#1}\par\smallskip}
\begin{document}"""]
    for index, example in enumerate(examples, 1):
        if index > 1:
            lines.append(r"\newpage")
        problem = example["reference"]
        identifier = example["id"].translate(TEX_ESCAPES)
        statement = example["statement"].translate(TEX_ESCAPES)
        lines += [
            r"{\small\color{heading}\textbf{VALIDATION DU PILOTE V2}}",
            rf"\section*{{Cas {index:02d}\enspace/\enspace {len(examples):02d}}}",
            rf"\texttt{{{identifier}}} \hfill Graine {example['seed']}",
            r"\rubrique{Énoncé d'origine}", statement, "",
            r"\textit{Pour cette validation, formuler le programme linéaire.}",
            r"\rubrique{Formulation en programmation linéaire}", _math_form(problem),
            r"\rubrique{JSON formulé}", r"{\small\begin{verbatim}",
            _compact_json(problem), r"\end{verbatim}}",
            r"\vfill\textbf{Validation de Marc}\quad\rule{0.62\linewidth}{0.4pt}",
        ]
    return "\n".join([*lines, r"\end{document}", ""])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, default=Path("runs/generation_pilot_v2/pilot.json"))
    parser.add_argument("--output", type=Path, default=REVIEW_DIR)
    args = parser.parse_args()

    examples = json.loads(args.pilot.read_text(encoding="utf-8"))["examples"]
    review = json.loads((REVIEW_DIR / "relecture.json").read_text(encoding="utf-8"))
    frozen = json.loads((REVIEW_DIR.parent / "pilot_v2.json").read_text(encoding="utf-8"))
    expected = review["references"]
    counts = {}
    results = {}
    input_issues = []
    for example in examples:
        identifier = example["id"]
        counts[identifier] = counts.get(identifier, 0) + 1
        if identifier not in expected:
            input_issues.append(f"`{identifier}` — transcription de référence manquante.")
            continue
        if review_fingerprint(example) != frozen[identifier]["sha256"]:
            input_issues.append(f"`{identifier}` — énoncé, graine ou JSON modifié depuis la revue du pilote.")
        results[identifier] = verify_lp(json.dumps(example["reference"]), _reference(expected[identifier]))
    for identifier in sorted(expected.keys() - counts.keys()):
        input_issues.append(f"`{identifier}` — cas absent du pilote.")
    for identifier, count in counts.items():
        if count > 1:
            input_issues.append(f"`{identifier}` — identifiant répété {count} fois.")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "rapport.md").write_text(
        _report(results, review["observations"], input_issues, review["marc_review"]),
        encoding="utf-8")
    if input_issues or any(result["issues"] for result in results.values()):
        raise SystemExit("Contrôle en échec. Voir rapport.md.")
    (args.output / "validation.tex").write_text(_booklet(examples), encoding="utf-8")


if __name__ == "__main__":
    main()
