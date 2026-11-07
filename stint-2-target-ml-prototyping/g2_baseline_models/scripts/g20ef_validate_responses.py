"""Read-only structural gate for g01-v2 external annotator responses."""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / "g2_baseline_models/internal/g20e_g20f_blind_catalogue_code_annotation"
LEVEL_ONE_EXITS = {"none_applicable", "ambiguous_multi_process", "abstain"}
ACTIVITY_EXITS = {"multiple", "no_applicable_code", "none_applicable", "abstain"}


def read_csv(path: Path, fields: list[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != fields:
            raise ValueError(f"Expected columns {fields}; got {reader.fieldnames}")
        rows = list(reader)
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise ValueError("Malformed CSV field count")
    return rows


def validate(target: str, annotator: str, response_path: Path) -> dict:
    stem = f"g20ef_{target}_g01-v2_{annotator}"
    package_dir = PRIVATE / "packages" / target / annotator
    package_path = package_dir / f"{stem}.jsonl"
    catalogue_path = package_dir / f"{stem}_catalogue_codes.csv"
    with package_path.open(encoding="utf-8") as handle:
        package = [json.loads(line) for line in handle]
    expected = {row["annotation_id"] for row in package}
    assert len(expected) == len(package)
    columns = ["annotation_id", "response"] if target == "activity" else [
        "annotation_id", "group", "code"
    ]
    rows = read_csv(response_path, columns)
    ids = [row["annotation_id"].strip() for row in rows]
    if len(rows) != len(package):
        raise ValueError(f"Row count {len(rows)} does not match package {len(package)}")
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate annotation_id")
    missing, extra = expected - set(ids), set(ids) - expected
    if missing or extra:
        raise ValueError(f"ID mismatch: missing={len(missing)}, extra={len(extra)}")

    catalogue = read_csv(catalogue_path, ["group", "code", "description"])
    counts = Counter()
    if target == "activity":
        allowed = {row["code"] for row in catalogue} | ACTIVITY_EXITS
        if not catalogue:
            raise ValueError("Catalogue code list is empty")
        for row in rows:
            answer = row["response"].strip()
            if answer not in allowed:
                raise ValueError(f"Invalid Activity response for {row['annotation_id']}")
            counts[answer] += 1
        abstentions = counts["abstain"]
        result = {"class_counts": dict(sorted(counts.items())), "abstentions": abstentions}
    else:
        if not catalogue:
            raise ValueError("Catalogue code list is empty")
        valid_pairs = {(row["group"], row["code"]) for row in catalogue}
        groups = {group for group, _ in valid_pairs}
        for row in rows:
            group, code = row["group"].strip(), row["code"].strip()
            if group in LEVEL_ONE_EXITS:
                if code:
                    raise ValueError(f"Level-1 exit must have blank code: {row['annotation_id']}")
                counts[group] += 1
            elif group in groups:
                if code == "abstain":
                    counts["code_abstain"] += 1
                elif (group, code) in valid_pairs:
                    counts[f"{group}|{code}"] += 1
                else:
                    raise ValueError(f"Invalid Damage group-code pair: {row['annotation_id']}")
            else:
                raise ValueError(f"Invalid Damage group: {row['annotation_id']}")
        result = {
            "level_one_exits": {key: counts[key] for key in sorted(LEVEL_ONE_EXITS)},
            "code_level_abstentions": counts["code_abstain"],
            "valid_group_code_responses": sum(
                value for key, value in counts.items() if "|" in key
            ),
        }
    if os.stat(response_path).st_mode & 0o077:
        raise ValueError("Response file must be private (mode 600)")
    return {
        "status": "valid",
        "target": target,
        "annotator": annotator,
        "rows": len(rows),
        **result,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("activity", "damage"), required=True)
    parser.add_argument("--annotator", choices=("annotator_01", "annotator_02"), required=True)
    parser.add_argument("--response", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(args.target, args.annotator, args.response), indent=2))


if __name__ == "__main__":
    main()
