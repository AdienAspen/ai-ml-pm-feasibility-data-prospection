from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[3]
F1_ROOT = PROJECT_ROOT / "stint-1-evidence-ground-truth" / "phase_1_lexical"
OUTPUTS_DIR = F1_ROOT / "outputs"
LEXICAL_V2 = OUTPUTS_DIR / "lexical_layer_v2" / "lexical_layer_v2_sanitized.csv"


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not LEXICAL_V2.exists():
        raise FileNotFoundError(f"Missing lexical v2 artifact: {LEXICAL_V2}")

    df = pd.read_csv(LEXICAL_V2)
    has_canonical_concept = "canonical_concept" in df.columns
    distinct_canonical_concepts = (
        int(df["canonical_concept"].nunique(dropna=True)) if has_canonical_concept else None
    )

    target_rows = []
    for target, group in df.groupby("target", dropna=False):
        target_rows.append(
            {
                "target": str(target),
                "rows": int(len(group)),
                "distinct_term_keys": int(group["term_key"].nunique()),
                "distinct_concept_ids": int(group["concept_id"].nunique()),
                "distinct_canonical_concepts": (
                    int(group["canonical_concept"].nunique(dropna=True))
                    if has_canonical_concept
                    else ""
                ),
                "canonical_concept_column_present": has_canonical_concept,
                "raw_values_emitted": False,
            }
        )
    target_rows.sort(key=lambda row: row["target"])

    status = (
        "grouping_not_demonstrated_missing_canonical_concept"
        if not has_canonical_concept
        else "grouping_measurable"
    )
    interpretation = (
        "F1 bootstrap filtered singleton unknown terms but did not yet produce a canonical_concept grouping field."
        if not has_canonical_concept
        else "F1 can be evaluated for term-to-concept collapse using canonical_concept counts."
    )

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": "F1b_grouping_readiness_check",
        "rows": int(len(df)),
        "distinct_term_keys": int(df["term_key"].nunique()),
        "distinct_concept_ids": int(df["concept_id"].nunique()),
        "canonical_concept_column_present": has_canonical_concept,
        "distinct_canonical_concepts": distinct_canonical_concepts,
        "status": status,
        "interpretation": interpretation,
        "lexical_layer_status": "provisional_pending_token_filtering_and_domain_grouping",
        "evaluation_independence_values": {
            str(k): int(v)
            for k, v in df["evaluation_independence"].value_counts(dropna=False).sort_index().items()
        },
        "raw_values_emitted": False,
        "outputs": {
            "summary_json": "stint-1-evidence-ground-truth/phase_1_lexical/outputs/f1b_grouping_readiness_summary.json",
            "target_csv": "stint-1-evidence-ground-truth/phase_1_lexical/outputs/f1b_grouping_readiness_by_target.csv",
            "memo": "stint-1-evidence-ground-truth/phase_1_lexical/outputs/f1b_grouping_readiness_memo.md",
        },
    }

    (OUTPUTS_DIR / "f1b_grouping_readiness_summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    write_csv(
        OUTPUTS_DIR / "f1b_grouping_readiness_by_target.csv",
        target_rows,
        [
            "target",
            "rows",
            "distinct_term_keys",
            "distinct_concept_ids",
            "distinct_canonical_concepts",
            "canonical_concept_column_present",
            "raw_values_emitted",
        ],
    )

    lines = [
        "# F1b - Grouping Readiness Check",
        "",
        "## Purpose",
        "",
        "This check answers whether F1 has demonstrated lexical grouping into canonical concepts.",
        "",
        "It emits counts only and no source-derived terms.",
        "",
        "## Result",
        "",
        f"- Rows checked: {summary['rows']}",
        f"- Distinct term keys: {summary['distinct_term_keys']}",
        f"- Distinct concept IDs: {summary['distinct_concept_ids']}",
        f"- `canonical_concept` column present: {summary['canonical_concept_column_present']}",
        f"- Distinct canonical concepts: {summary['distinct_canonical_concepts']}",
        f"- Status: `{summary['status']}`",
        "",
        "## Interpretation",
        "",
        summary["interpretation"],
        "",
        "`LEXICAL_LAYER` remains `provisional_pending_token_filtering_and_domain_grouping`.",
        "",
        "The current F1 output is a filtered working layer. It is not yet evidence that variants have collapsed into a smaller domain-concept inventory.",
        "",
        "## Evaluation Boundary",
        "",
        "All lexical rows remain `derived_from_rules`; they are not a held-out evaluation set for STINT_2.",
    ]
    (OUTPUTS_DIR / "f1b_grouping_readiness_memo.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
