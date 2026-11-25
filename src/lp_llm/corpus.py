"""Generate deterministic splits from the approved library, or draft them for review."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import platform
import re
from string import Formatter

import scipy

from lp_llm.generate import check_admission, render_statement, sample_reference
from lp_llm.solver import solve_lp_problem
from lp_llm.verify import constraint_key

SPLITS = ("train", "validation", "test")
SENSES = {"production": ("max", "<="), "mixing": ("min", ">=")}


def validate_templates(templates: list, preview: bool) -> None:
    """Check fixed fields, units and disjoint lineages before drawing references."""
    ids = set()
    lineages = {}
    groups = set()
    for template in templates:
        identifier = template["template_id"]
        split, family, size = (template[key] for key in ("split", "family", "constraint_count"))
        if (identifier in ids or split not in SPLITS or family not in SENSES
                or size not in (2, 3) or not template["lineage_id"]):
            raise ValueError(f"{identifier}: invalid or duplicate template registration")
        if template["status"] not in (("accepted", "needs_review") if preview else ("accepted",)):
            raise ValueError(f"{identifier}: template is not approved for this run")
        ids.add(identifier)
        groups.add((split, family, size))
        lineage = template["lineage_id"]
        if lineages.setdefault(lineage, split) != split:
            raise ValueError(f"{lineage}: lineage assigned to more than one split")

        parsed = list(Formatter().parse(template["text"]))
        fields = [name for _, name, _, _ in parsed if name is not None]
        required = {"objective_x1", "objective_x2"}
        for i in range(1, size + 1):
            required.update((f"constraint_{i}_x1", f"constraint_{i}_x2", f"rhs_{i}"))
        literals = "".join(literal for literal, _, _, _ in parsed)
        units = [variable["unit"] for variable in template["variables"]]
        objective = template["objective"]
        if (set(fields) != required or any(spec or conversion for _, _, spec, conversion in parsed)
                or re.search(r"[0-9]", re.sub(r"\bx[12]\b", "", literals))
                or any(value in literals for value in (identifier, lineage, "{", "}", "```"))
                or [variable["name"] for variable in template["variables"]] != ["x1", "x2"]
                or objective["sense"] != SENSES[family][0]
                or objective["coefficient_fields"] != ["objective_x1", "objective_x2"]
                or objective["coefficient_units"] != [f"{objective['unit']}/{unit}" for unit in units]):
            raise ValueError(f"{identifier}: invalid statement fields or objective metadata")
        order = list(dict.fromkeys(int(field.split("_")[1]) for field in fields
                                   if field.startswith(("constraint_", "rhs_"))))
        if (template["constraint_order_in_text"] != order
                or len(template["constraint_mapping"]) != size):
            raise ValueError(f"{identifier}: invalid constraint order or mapping")
        for i, row in enumerate(template["constraint_mapping"], 1):
            if (row["position"] != i or row["reference_constraint_index"] != i - 1
                    or row["sense"] != SENSES[family][1]
                    or row["coefficient_fields"] != [f"constraint_{i}_x1", f"constraint_{i}_x2"]
                    or row["coefficient_units"] != [f"{row['rhs_unit']}/{unit}" for unit in units]
                    or row["rhs_field"] != f"rhs_{i}"):
                raise ValueError(f"{identifier}: inconsistent constraint {i} metadata")
    required_groups = {(split, family, size)
                       for split in SPLITS for family in SENSES for size in (2, 3)}
    if groups != required_groups:
        raise ValueError(f"Missing template groups {sorted(required_groups - groups)}")


def formulation_key(reference: dict) -> tuple:
    """Ignore row order, positive rescaling and equivalent inequality signs."""
    objective = reference["objective"]
    coefficients = tuple(Fraction(str(value)) for value in objective["coefficients"])
    scale = next((abs(value) for value in coefficients if value), Fraction(1))
    return (tuple(reference["variables"]), tuple(map(tuple, reference["bounds"])),
            objective["sense"], tuple(value / scale for value in coefficients),
            tuple(sorted(map(constraint_key, reference["constraints"]))))


def generate_splits(config: dict, profile: dict, templates: list, held_out: list) -> tuple:
    quotas = profile["per_family_and_size"]
    target = profile["test_interior_per_family_and_size"]
    tolerance = profile["positive_variable_tolerance"]
    if not 0 < target < quotas["test"] or min(quotas.values()) < 2 or tolerance <= 0:
        raise ValueError("Invalid split quotas or geometry target")
    max_attempts = config["generation"]["max_attempts_per_example"]
    seed = profile["master_seed"]
    references = {formulation_key(case["reference"]) for case in held_out}
    statements = {" ".join(case["statement"].casefold().split()) for case in held_out}
    splits = {split: [] for split in SPLITS}
    counts = Counter()
    rejected = Counter()
    for split in SPLITS:
        for family in SENSES:
            for size in (2, 3):
                group = f"{split}/{family}/{size}"
                options = [item for item in templates
                           if (item["split"], item["family"], item["constraint_count"])
                           == (split, family, size)]
                for index in range(quotas[split]):
                    template = options[index % len(options)]
                    desired = "interior" if index < target else "axis"
                    failures = Counter()
                    for _ in range(max_attempts):
                        current, seed = seed, seed + 1
                        reference = sample_reference(family, size, current, config)
                        result = solve_lp_problem(json.dumps(reference, allow_nan=False))
                        admission = check_admission(reference, result, config["admission"])
                        if not admission["accepted"]:
                            failures[admission["reason"]] += 1
                            continue
                        geometry = "interior" if min(result["solution"]) > tolerance else "axis"
                        if split == "test" and geometry != desired:
                            failures["geometry"] += 1
                            continue
                        key = formulation_key(reference)
                        statement = render_statement(template, reference)
                        text_key = " ".join(statement.casefold().split())
                        if key in references or text_key in statements:
                            failures["duplicate"] += 1
                            continue
                        references.add(key)
                        statements.add(text_key)
                        counts[group, geometry] += 1
                        splits[split].append({
                            "id": f"{split}_{family}_{size}c_{index + 1:03d}",
                            "split": split, "family": family, "seed": current,
                            "template_id": template["template_id"], "lineage_id": template["lineage_id"],
                            "statement": statement, "reference": reference,
                        })
                        break
                    else:
                        raise ValueError(f"{group} example {index + 1}: exhausted seeds through "
                                         f"{seed - 1}; rejections {dict(failures)}")
                    rejected.update(failures)
    return splits, {
        "seed_start": profile["master_seed"], "next_seed": seed,
        "geometry_by_group": {f"{group}/{geometry}": n for (group, geometry), n in counts.items()},
        "rejections": dict(rejected),
    }


def review_markdown(templates: list, splits: dict) -> str:
    lines = [
        "# Relecture des gabarits du corpus v1", "",
        "Chaque gabarit a un rendu à valeurs distinctes, puis deux exemples issus du corpus. "
        "Vérifier l'ordre des variables, la correspondance de chaque valeur, les unités et "
        "le sens de l'objectif et des contraintes. Les bornes se lisent toujours x1 ≥ 0 et x2 ≥ 0.", "",
        "Les gabarits et leurs affectations sont contrôlés automatiquement. "
        "La relecture de Marc reste à consigner.", "",
    ]
    for template in templates:
        identifier = template["template_id"]
        size = template["constraint_count"]
        sense, relation = SENSES[template["family"]]
        diagnostic = {
            "variables": ["x1", "x2"], "bounds": [[0, None], [0, None]],
            "objective": {"sense": sense, "coefficients": [11, 13]},
            "constraints": [{"coefficients": [17 + 2*i, 18 + 2*i], "sense": relation, "rhs": 101 + i}
                            for i in range(size)],
        }
        examples = [(case["id"], case["statement"], case["reference"])
                    for case in splits[template["split"]] if case["template_id"] == identifier]
        lines.extend([f"## {identifier}", "", f"Lot `{template['split']}` · "
                      f"{size} contraintes · {len(examples)} exemples", ""])
        for label, text, ref in [
            ("Diagnostic", render_statement(template, diagnostic), diagnostic),
            *examples[:2],
        ]:
            objective = ref["objective"]
            a, b = objective["coefficients"]
            lines.extend([f"### {label}", "", "```text", text, "```", "", "```text",
                          f"{objective['sense']} {a} x1 + {b} x2", "s.t."])
            for row in ref["constraints"]:
                a, b = row["coefficients"]
                lines.append(f"    {a} x1 + {b} x2 {row['sense']} {row['rhs']}")
            lines.extend(["    x1 >= 0, x2 >= 0", "```", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or (Path("runs/corpus_v1_preview") if args.preview else Path("data"))
    if args.preview and output.resolve() == Path("data").resolve():
        parser.error("Use a separate output directory for draft splits.")
    names = [f"{split}.jsonl" for split in SPLITS] + ["corpus_v1_manifest.json", "relecture.md"]
    if any((output / name).exists() for name in names):
        parser.error("Output files already exist. Choose another --output.")
    template_path = Path("templates/corpus_v1_candidates.json" if args.preview else "templates/accepted.json")
    corpus_path = Path("configs/corpus_v1.json")
    numeric_path = Path("configs/generate_v1.json")
    held_out_path = Path("data/human_test.jsonl")
    inputs = {path: path.read_text(encoding="utf-8")
              for path in (template_path, corpus_path, numeric_path, held_out_path)}
    templates = json.loads(inputs[template_path])
    if not templates and not args.preview:
        parser.error("The approved library is empty. Use --preview to generate review samples.")
    profile = json.loads(inputs[corpus_path])
    config = json.loads(inputs[numeric_path])
    held_out = [json.loads(line) for line in inputs[held_out_path].splitlines()]
    validate_templates(templates, args.preview)
    splits, summary = generate_splits(config, profile, templates, held_out)
    manifest = {
        "preview": args.preview,
        "python": platform.python_version(), "scipy": scipy.__version__,
        "input_sha256_utf8_lf": {p.as_posix(): sha256(s.encode("utf-8")).hexdigest()
                                for p, s in inputs.items()},
        "template_assignments": [{key: row[key] for key in ("template_id", "lineage_id", "split")}
                                 for row in templates],
        "by_template": dict(Counter(case["template_id"] for rows in splits.values() for case in rows)),
        **summary,
        "files": {},
    }
    output.mkdir(parents=True, exist_ok=True)
    for split, rows in splits.items():
        name = f"{split}.jsonl"
        content = "".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in rows)
        with (output / name).open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        manifest["files"][name] = {"examples": len(rows), "sha256": sha256(content.encode("utf-8")).hexdigest()}
    if args.preview:
        (output / "relecture.md").write_text(review_markdown(templates, splits), encoding="utf-8")
    (output / "corpus_v1_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest["files"], indent=2))


if __name__ == "__main__":
    main()
