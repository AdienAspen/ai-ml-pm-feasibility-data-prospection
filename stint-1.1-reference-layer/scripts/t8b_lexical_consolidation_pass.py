from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
STINT_ROOT = PROJECT_ROOT / "stint-1.1-reference-layer"
LEXICAL_DIR = STINT_ROOT / "reference_layer" / "lexical_layer"
OUTPUTS_DIR = STINT_ROOT / "outputs"
DOCS_DIR = STINT_ROOT / "docs"

RAW_DICTIONARY = LEXICAL_DIR / "lexical_seed_dictionary_v1.csv"
SANITIZED_DICTIONARY = LEXICAL_DIR / "lexical_seed_dictionary_v1_sanitized.csv"


# Public adaptation: the controlled abbreviation map is not distributed.
ABBREVIATIONS = {}

SUFFIXES = (
    "ing",
    "ed",
    "es",
    "s",
)


def stable_key(value: object, prefix: str) -> str:
    raw = "" if value is None or pd.isna(value) else str(value)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def normalize_token(token: str) -> str:
    token = token.lower().strip()
    token = ABBREVIATIONS.get(token, token)
    if token in ABBREVIATIONS:
        return ABBREVIATIONS[token]
    for suffix in SUFFIXES:
        if len(token) > len(suffix) + 4 and token.endswith(suffix):
            candidate = token[: -len(suffix)]
            return ABBREVIATIONS.get(candidate, candidate)
    return token


def consolidate_term(term: str) -> str:
    tokens = [normalize_token(t) for t in re.split(r"\s+", str(term).lower().strip()) if t]
    if not tokens:
        return ""
    # Collapse immediate duplicates created by abbreviation/suffix normalization.
    collapsed = []
    for token in tokens:
        if not collapsed or collapsed[-1] != token:
            collapsed.append(token)
    return " ".join(collapsed)


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not RAW_DICTIONARY.exists():
        raise FileNotFoundError(f"Missing local-only working dictionary: {RAW_DICTIONARY}")

    raw_df = pd.read_csv(RAW_DICTIONARY)
    sanitized_df = pd.read_csv(SANITIZED_DICTIONARY)

    if "observed_term_key" not in raw_df.columns:
        raw_df["observed_term_key"] = raw_df["observed_term"].map(lambda value: stable_key(value, "TERM"))
    if "normalised_term_key" not in raw_df.columns:
        raw_df["normalised_term_key"] = raw_df["normalised_term"].map(lambda value: stable_key(value, "TERM"))

    raw_df["consolidated_term"] = raw_df["observed_term"].map(consolidate_term)
    raw_df["consolidated_term_key"] = raw_df["consolidated_term"].map(lambda value: stable_key(value, "TERM"))

    dimensions = [
        "consolidated_term_key",
        "canonical_concept",
        "target",
        "namespace",
        "target_field",
        "source_text_field",
        "stratum",
        "contractor_path",
        "observed_term_origin",
        "target_assignment_evidence_type",
        "evidence_type",
        "tier",
        "status",
        "language_hint",
    ]

    grouped_rows: list[dict] = []
    for key, group in raw_df.groupby(dimensions, dropna=False):
        row = dict(zip(dimensions, key))
        row["concept_id"] = stable_key("|".join(str(v) for v in key), "LEXC")
        row["observed_variant_count"] = int(group["observed_term_key"].nunique())
        row["source_row_count"] = int(len(group))
        row["record_count"] = int(group["record_count"].sum())
        row["site_count_max"] = int(group["site_count"].max())
        row["contains_source_derived_terms"] = False
        row["raw_values_emitted"] = False
        grouped_rows.append(row)

    grouped_rows.sort(key=lambda row: (-row["record_count"], row["target"], row["consolidated_term_key"]))

    write_csv(
        LEXICAL_DIR / "lexical_seed_dictionary_v1_consolidated_raw.csv",
        [
            {
                **row,
                "consolidated_term": group_key,
            }
            for group_key, row in []
        ],
        ["consolidated_term"],
    )
    # The raw consolidated file is intentionally local-only; it exists only as a marker
    # because the source-derived terms remain in the original working dictionary.

    write_csv(
        LEXICAL_DIR / "lexical_seed_dictionary_v1_consolidated_sanitized.csv",
        grouped_rows,
        [
            "concept_id",
            "consolidated_term_key",
            "canonical_concept",
            "target",
            "namespace",
            "target_field",
            "source_text_field",
            "stratum",
            "contractor_path",
            "observed_variant_count",
            "source_row_count",
            "record_count",
            "site_count_max",
            "observed_term_origin",
            "target_assignment_evidence_type",
            "evidence_type",
            "tier",
            "status",
            "language_hint",
            "contains_source_derived_terms",
            "raw_values_emitted",
        ],
    )

    initial_rows = len(sanitized_df)
    initial_observed = int(sanitized_df["observed_term_key"].nunique())
    initial_normalized = int(sanitized_df["normalised_term_key"].nunique())
    consolidated_keys = int(raw_df["consolidated_term_key"].nunique())
    consolidated_rows = len(grouped_rows)
    target_summary = Counter(row["target"] for row in grouped_rows)
    status_summary = Counter(row["status"] for row in grouped_rows)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "task": "T8b_lexical_consolidation_pass",
        "initial_rows": initial_rows,
        "initial_distinct_observed_term_keys": initial_observed,
        "initial_distinct_normalised_term_keys": initial_normalized,
        "consolidated_distinct_term_keys": consolidated_keys,
        "consolidated_contextual_rows": consolidated_rows,
        "initial_observed_equals_normalised": initial_observed == initial_normalized,
        "row_reduction_pct": round(100.0 * (initial_rows - consolidated_rows) / initial_rows, 2) if initial_rows else 0.0,
        "distinct_term_reduction_pct": round(100.0 * (initial_observed - consolidated_keys) / initial_observed, 2) if initial_observed else 0.0,
        "target_summary": dict(target_summary),
        "status_summary": dict(status_summary),
        "lexical_artifact_status": "provisional_pending_manual_review",
        "heuristic_target_range": "300-800 canonical concepts is a sanity heuristic, not a requirement",
        "raw_values_emitted": False,
        "outputs": {
            "consolidated_sanitized_csv": "stint-1.1-reference-layer/reference_layer/lexical_layer/lexical_seed_dictionary_v1_consolidated_sanitized.csv",
            "summary_json": "stint-1.1-reference-layer/outputs/t8b_lexical_consolidation_summary_v1.json",
            "memo": "stint-1.1-reference-layer/docs/t8b_lexical_consolidation_pass.md",
        },
    }
    (OUTPUTS_DIR / "t8b_lexical_consolidation_summary_v1.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )

    lines = [
        "# T8b - Lexical Consolidation Pass",
        "",
        "## Purpose",
        "",
        "This pass reconciles Chapter #1 and Chapter #2 feedback on T8 before freezing the reference layer.",
        "",
        "It measures whether the T8 artefact is a convergent lexical dictionary or a broad vocabulary dump, then applies conservative abbreviation/suffix consolidation without exposing source-derived terms.",
        "",
        "## Measured Collapse",
        "",
        f"- Initial rows: {summary['initial_rows']}",
        f"- Distinct observed term keys: {summary['initial_distinct_observed_term_keys']}",
        f"- Distinct normalised term keys: {summary['initial_distinct_normalised_term_keys']}",
        f"- Observed keys equal normalised keys: {summary['initial_observed_equals_normalised']}",
        f"- Consolidated distinct term keys: {summary['consolidated_distinct_term_keys']}",
        f"- Consolidated contextual rows: {summary['consolidated_contextual_rows']}",
        f"- Row reduction: {summary['row_reduction_pct']}%",
        f"- Distinct-term reduction: {summary['distinct_term_reduction_pct']}%",
        "",
        "## Interpretation",
        "",
        "The warning is confirmed: the original T8 output behaves more like a broad vocabulary dump than a compact seed dictionary. The equality between observed and normalised term keys shows that little lexical convergence occurred in T8 itself.",
        "",
        "T8b improves the artefact through conservative consolidation, but the result remains provisional. It should not be frozen in T9 as final lexical truth without manual/domain review and downstream evidence triangulation.",
        "",
        "## Governance",
        "",
        "- `source_text_field` remains mandatory.",
        "- `stratum` remains mandatory and `event_structural` must not be mixed with planned/reactive strata.",
        "- Target assignment remains `expert_inference` unless independently validated later.",
        "- `Symptom` entries are candidate symptom-like lexical signal, not Catalog S proof-of-life.",
        "- The 300-800 concept range is a sanity heuristic, not a hard requirement.",
        "- No raw source-derived terms are emitted in the versioned consolidated artefact.",
        "",
        "## Outputs",
        "",
        "- `reference_layer/lexical_layer/lexical_seed_dictionary_v1_consolidated_sanitized.csv`",
        "- `outputs/t8b_lexical_consolidation_summary_v1.json`",
    ]
    (DOCS_DIR / "t8b_lexical_consolidation_pass.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
