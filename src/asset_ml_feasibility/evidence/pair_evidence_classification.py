from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = PROJECT_ROOT / "reports"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

PAIR_DISCOVERY_PATH = REPORTS_DIR / "safe_content_pair_discovery_sanitized.csv"
PAIR_CLASSIFICATION_PATH = REPORTS_DIR / "pair_evidence_classification_sanitized.csv"
TARGET_REVIEW_PATH = REPORTS_DIR / "target_pair_review_sanitized.csv"
SUMMARY_PATH = ARTIFACTS_DIR / "pair_evidence_classification_summary_sanitized.json"

TARGET_ORDER = [
    "Symptom",
    "Object Part",
    "Damage",
    "Cause",
    "Activity",
    "FLOC leaf segment",
    "Activity Type",
]

EVIDENCE_TYPES = [
    "real_observed_label",
    "validated_mapping",
    "illustrative_example",
    "reference_catalog",
    "agent_inference",
    "unknown",
]

MEASUREMENT_READY_TYPES = {"real_observed_label", "validated_mapping"}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv_if_present(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    return pd.read_csv(path)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def split_target_hint(value: Any) -> list[str]:
    text = str(value or "").strip()
    if not text or text.lower() == "nan":
        return ["unknown"]
    targets = [part.strip() for part in text.split(";") if part.strip()]
    return targets or ["unknown"]


def classify_pair(row: pd.Series, target: str) -> dict[str, Any]:
    if target == "unknown":
        evidence_type = "unknown"
        confidence = "not_classified"
        target_relevance = "requires_semantic_reconciliation"
        blocker_reason = "target_not_attributed"
        review_priority = "high"
        needs_target_reclassification = True
        needs_controlled_vocabulary_review = True
    else:
        evidence_type = "agent_inference"
        confidence = "metadata_or_overlap_inferred"
        target_relevance = "candidate_for_target_review"
        blocker_reason = "record_level_label_or_validated_mapping_required"
        review_priority = "medium"
        needs_target_reclassification = False
        needs_controlled_vocabulary_review = target in {"Activity Type", "FLOC leaf segment"}

    if target == "Activity Type":
        blocker_reason = "controlled_ge_mat_source_required_before_measurement"
        review_priority = "high"
    elif target == "Symptom":
        blocker_reason = "symptom_requires_explicit_proof_of_life_review"
        review_priority = "high"

    can_support_measurement = evidence_type in MEASUREMENT_READY_TYPES

    return {
        "target": target,
        "target_relevance": target_relevance,
        "evidence_type": evidence_type,
        "classification_confidence": confidence,
        "can_support_measurement": can_support_measurement,
        "blocker_reason": blocker_reason,
        "review_priority": review_priority,
        "needs_target_reclassification": needs_target_reclassification,
        "needs_controlled_vocabulary_review": needs_controlled_vocabulary_review,
        "needs_runtime_validation": True,
        "needs_label_validation": True,
        "package_id": row.get("package_id", ""),
        "path_hash": row.get("path_hash", ""),
        "sheet_hash": row.get("sheet_hash", ""),
        "pair_hash": row.get("pair_hash", ""),
        "extension": row.get("extension", ""),
        "data_family": row.get("data_family", ""),
        "likely_role": row.get("likely_role", ""),
        "source_target_hint": row.get("target_hint", ""),
        "cooccurring_rows": row.get("cooccurring_rows", 0),
        "cooccurrence_rate": row.get("cooccurrence_rate", 0),
        "code_distinct_count": row.get("code_distinct_count", 0),
        "text_distinct_count": row.get("text_distinct_count", 0),
        "mean_text_length": row.get("mean_text_length", 0),
        "mean_code_length": row.get("mean_code_length", 0),
        "row_level_validation_performed": False,
        "raw_operational_values_emitted": False,
    }


def build_classification_rows(pair_rows: pd.DataFrame) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    if pair_rows.empty:
        return output
    for _, row in pair_rows.iterrows():
        for target in split_target_hint(row.get("target_hint", "unknown")):
            output.append(classify_pair(row, target))
    return output


def build_target_review(classified: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for target in TARGET_ORDER + ["unknown"]:
        subset = classified[classified["target"] == target] if not classified.empty else pd.DataFrame()
        evidence_counts = Counter(subset["evidence_type"]) if not subset.empty else Counter()
        measurement_ready = int(subset["can_support_measurement"].fillna(False).astype(bool).sum()) if not subset.empty else 0
        candidate_count = int(len(subset))
        row_level_pair_count = int(pd.to_numeric(subset.get("cooccurring_rows", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not subset.empty else 0
        distinct_files = int(subset["path_hash"].nunique()) if not subset.empty and "path_hash" in subset.columns else 0

        if measurement_ready:
            interpretation = "measurement_candidate_requires_final_runtime_and_label_confirmation"
        elif candidate_count and target == "unknown":
            interpretation = "unattributed_pair_opportunities_require_semantic_reconciliation"
        elif candidate_count:
            interpretation = "candidate_pairs_are_inferred_not_measurement_ready"
        else:
            interpretation = "no_pair_opportunity_attributed_in_this_pass"

        if target == "Activity Type" and candidate_count:
            interpretation = "activity_type_candidates_blocked_until_controlled_ge_mat_source_confirmed"
        if target == "Symptom" and candidate_count == 0:
            interpretation = "no_symptom_pair_opportunity_attributed_in_this_pass"

        rows.append(
            {
                "target": target,
                "classified_pair_rows": candidate_count,
                "row_level_pair_count": row_level_pair_count,
                "distinct_files": distinct_files,
                "measurement_ready_pair_rows": measurement_ready,
                "real_observed_label_rows": int(evidence_counts.get("real_observed_label", 0)),
                "validated_mapping_rows": int(evidence_counts.get("validated_mapping", 0)),
                "reference_catalog_rows": int(evidence_counts.get("reference_catalog", 0)),
                "agent_inference_rows": int(evidence_counts.get("agent_inference", 0)),
                "unknown_evidence_rows": int(evidence_counts.get("unknown", 0)),
                "interpretation": interpretation,
                "raw_operational_values_emitted": False,
            }
        )
    return rows


def run_pair_evidence_classification() -> dict[str, Any]:
    pair_rows = read_csv_if_present(PAIR_DISCOVERY_PATH)
    classified_rows = build_classification_rows(pair_rows)
    write_csv(PAIR_CLASSIFICATION_PATH, classified_rows)

    classified = pd.DataFrame(classified_rows)
    target_review_rows = build_target_review(classified)
    write_csv(TARGET_REVIEW_PATH, target_review_rows)

    evidence_counts = Counter(classified["evidence_type"]) if not classified.empty else Counter()
    target_counts = Counter(classified["target"]) if not classified.empty else Counter()
    measurement_ready_rows = (
        int(classified["can_support_measurement"].fillna(False).astype(bool).sum())
        if not classified.empty
        else 0
    )

    summary = {
        "created_at_utc": now_utc(),
        "input_pair_opportunities": int(len(pair_rows)),
        "classified_pair_rows": int(len(classified_rows)),
        "measurement_ready_pair_rows": measurement_ready_rows,
        "evidence_type_counts": {key: int(evidence_counts.get(key, 0)) for key in EVIDENCE_TYPES},
        "target_classification_counts": {
            target: int(target_counts.get(target, 0)) for target in TARGET_ORDER + ["unknown"]
        },
        "settings": {
            "method_scope": "safe_pair_opportunity_evidence_classification",
            "classification_is_conservative": True,
            "only_measurement_ready_types": sorted(MEASUREMENT_READY_TYPES),
            "metadata_inference_is_not_ground_truth": True,
            "row_level_validation_performed": False,
            "runtime_validation_performed": False,
            "raw_values_emitted_in_versionable_outputs": False,
        },
        "outputs": {
            "pair_evidence_classification_csv": str(PAIR_CLASSIFICATION_PATH.relative_to(PROJECT_ROOT)),
            "target_pair_review_csv": str(TARGET_REVIEW_PATH.relative_to(PROJECT_ROOT)),
        },
        "raw_operational_values_emitted": False,
    }

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(run_pair_evidence_classification(), indent=2))
