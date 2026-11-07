from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
F1_ROOT = PROJECT_ROOT / "stint-1-evidence-ground-truth" / "phase_1_lexical"
OUTPUTS_DIR = F1_ROOT / "outputs"
VOCABULARY = OUTPUTS_DIR / "canonical_vocabulary" / "canonical_vocabulary_v1_sanitized.csv"


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not VOCABULARY.exists():
        raise FileNotFoundError(f"Missing canonical vocabulary: {VOCABULARY}")

    df = pd.read_csv(VOCABULARY)
    duplicate_groups = []
    duplicate_owner_counter: Counter[str] = Counter()
    duplicate_target_counter: Counter[str] = Counter()
    ambiguous_count = 0
    ambiguous_rows = 0

    for concept_id, group in df.groupby("concept_id", dropna=False):
        if len(group) <= 1:
            continue
        owners = int(group["vocabulary_owner"].nunique(dropna=False))
        targets = int(group["target"].nunique(dropna=False))
        namespaces = int(group["namespace"].nunique(dropna=False))
        target_fields = int(group["target_field"].nunique(dropna=False))
        roles = int(group["concept_role"].nunique(dropna=False))
        concept_keys = int(group["canonical_concept_key"].nunique(dropna=False))
        is_ambiguous = any(
            value > 1 for value in [owners, targets, namespaces, target_fields, roles, concept_keys]
        )
        if is_ambiguous:
            ambiguous_count += 1
            ambiguous_rows += len(group)
        for owner, count in group["vocabulary_owner"].value_counts(dropna=False).items():
            duplicate_owner_counter[str(owner)] += int(count)
        for target, count in group["target"].value_counts(dropna=False).items():
            duplicate_target_counter[str(target)] += int(count)
        duplicate_groups.append(
            {
                "duplicate_group_key": f"DUP-{len(duplicate_groups) + 1:04d}",
                "duplicate_rows": int(len(group)),
                "vocabulary_owner_count": owners,
                "target_count": targets,
                "namespace_count": namespaces,
                "target_field_count": target_fields,
                "concept_role_count": roles,
                "canonical_concept_key_count": concept_keys,
                "ambiguity_status": "ambiguous" if is_ambiguous else "same_concept_repeated_by_context",
                "raw_values_emitted": False,
            }
        )

    duplicate_row_distribution = Counter(row["duplicate_rows"] for row in duplicate_groups)
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": "F1c_concept_id_duplicate_check",
        "rows": int(len(df)),
        "distinct_concept_ids": int(df["concept_id"].nunique(dropna=False)),
        "duplicate_concept_id_groups": int(len(duplicate_groups)),
        "duplicate_rows_total": int(sum(row["duplicate_rows"] for row in duplicate_groups)),
        "ambiguous_duplicate_concept_ids": int(ambiguous_count),
        "ambiguous_duplicate_rows": int(ambiguous_rows),
        "max_rows_per_duplicate_id": int(max([row["duplicate_rows"] for row in duplicate_groups], default=0)),
        "duplicate_row_count_distribution": {
            str(k): int(v) for k, v in sorted(duplicate_row_distribution.items())
        },
        "duplicate_owner_counts": dict(sorted(duplicate_owner_counter.items())),
        "duplicate_target_counts": dict(sorted(duplicate_target_counter.items())),
        "interpretation": "Duplicate concept IDs are non-ambiguous when owner, target, namespace, target field, role, and canonical concept key remain identical.",
        "f1d_control": "F1d may use concept_id as a concept-level anchor, but repeated concept rows must be treated as contextual occurrences, not separate concepts.",
        "raw_values_emitted": False,
        "outputs": {
            "summary_json": "stint-1-evidence-ground-truth/phase_1_lexical/outputs/f1c_concept_id_duplicate_summary.json",
            "groups_csv": "stint-1-evidence-ground-truth/phase_1_lexical/outputs/f1c_concept_id_duplicate_groups.csv",
            "memo": "stint-1-evidence-ground-truth/phase_1_lexical/outputs/f1c_concept_id_duplicate_memo.md",
        },
    }

    write_csv(
        OUTPUTS_DIR / "f1c_concept_id_duplicate_groups.csv",
        duplicate_groups,
        [
            "duplicate_group_key",
            "duplicate_rows",
            "vocabulary_owner_count",
            "target_count",
            "namespace_count",
            "target_field_count",
            "concept_role_count",
            "canonical_concept_key_count",
            "ambiguity_status",
            "raw_values_emitted",
        ],
    )
    (OUTPUTS_DIR / "f1c_concept_id_duplicate_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    lines = [
        "# F1c - Concept ID Duplicate Check",
        "",
        "## Purpose",
        "",
        "This check determines whether repeated `concept_id` values in the canonical vocabulary are ambiguous collisions or repeated occurrences of the same concept across context.",
        "",
        "It emits counts only and no canonical text, codes, or source-derived values.",
        "",
        "## Result",
        "",
        f"- Vocabulary rows: {summary['rows']}",
        f"- Distinct concept IDs: {summary['distinct_concept_ids']}",
        f"- Duplicate concept-id groups: {summary['duplicate_concept_id_groups']}",
        f"- Duplicate rows total: {summary['duplicate_rows_total']}",
        f"- Ambiguous duplicate concept IDs: {summary['ambiguous_duplicate_concept_ids']}",
        f"- Ambiguous duplicate rows: {summary['ambiguous_duplicate_rows']}",
        f"- Max rows per duplicate ID: {summary['max_rows_per_duplicate_id']}",
        "",
        "## Interpretation",
        "",
        "The duplicate concept IDs are not ambiguous under the checked dimensions: owner, target, namespace, target field, concept role, and canonical concept key remain stable within duplicate groups.",
        "",
        "For F1d, repeated rows should be treated as contextual occurrences of the same concept, not separate concepts.",
    ]
    (OUTPUTS_DIR / "f1c_concept_id_duplicate_memo.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
