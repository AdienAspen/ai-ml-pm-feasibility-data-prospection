from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = PROJECT_ROOT / "reports"
INTERNAL_REPORTS_DIR = REPORTS_DIR / "internal"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INTERNAL_ARTIFACTS_DIR = ARTIFACTS_DIR / "internal"
STRUCTURAL_SCAN_PATH = INTERNAL_REPORTS_DIR / "basic_structural_scan.csv"

TEXT_HINTS = (
    "text",
    "description",
    "desc",
    "note",
    "notes",
    "comment",
    "comments",
    "event",
    "summary",
    "problem",
    "reason",
    "cause",
    "damage",
    "activity",
    "symptom",
    "fault",
    "message",
    "notification",
    "long_text",
    "short_text",
)
ID_HINTS = (
    "id",
    "code",
    "number",
    "num",
    "key",
    "order",
    "notification",
    "equipment",
    "asset",
    "serial",
    "tag",
)
SITE_HINTS = ("site", "plant", "location")
ASSET_HINTS = ("equipment", "asset")
DATE_HINTS = ("date", "time", "timestamp", "created", "updated", "start", "end", "month", "year")
CATALOG_HINTS = ("catalog", "catalogue", "code group", "code_group", "group", "symptom", "damage", "cause", "activity", "object part")
RUNTIME_SOURCE_ROLES = {"source_data"}
REFERENCE_ROLES = {"reference_data", "mapping_doc", "canonical_doc", "architecture_doc"}


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_name(value: str) -> str:
    value = value or ""
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def safe_json_loads(value: str, fallback: Any) -> Any:
    if value is None or value == "":
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def contains_any(normalized: str, hints: tuple[str, ...]) -> bool:
    return any(normalize_name(hint) in normalized for hint in hints)


def is_placeholder_column(normalized: str) -> bool:
    if not normalized or normalized == "nan":
        return True
    return normalized.startswith("unnamed_")


def infer_column_profile(column_name: str, dtype: str, null_rate: Any) -> dict[str, Any]:
    normalized = normalize_name(column_name)
    dtype_norm = (dtype or "").lower()
    null_value = None
    try:
        null_value = float(null_rate) if null_rate is not None else None
    except (TypeError, ValueError):
        null_value = None

    is_placeholder = is_placeholder_column(normalized)
    is_string_like_dtype = "object" in dtype_norm or "string" in dtype_norm
    has_text_name_signal = contains_any(normalized, TEXT_HINTS)
    is_id = contains_any(normalized, ID_HINTS)
    is_site = contains_any(normalized, SITE_HINTS)
    is_asset = contains_any(normalized, ASSET_HINTS)
    is_date = contains_any(normalized, DATE_HINTS) or "date" in dtype_norm or "time" in dtype_norm
    is_catalog_signal = contains_any(normalized, CATALOG_HINTS)
    is_text = has_text_name_signal and not is_placeholder and not is_id

    candidate_bucket = "other"
    if not is_placeholder:
        if is_text:
            candidate_bucket = "candidate_text"
        elif is_id:
            candidate_bucket = "candidate_id_or_code"
        elif is_date:
            candidate_bucket = "candidate_date"
        elif is_site:
            candidate_bucket = "candidate_site"
        elif is_asset:
            candidate_bucket = "candidate_asset"

    if null_value is None:
        null_bucket = "unknown"
    elif null_value == 0:
        null_bucket = "none"
    elif null_value <= 0.25:
        null_bucket = "low"
    elif null_value <= 0.75:
        null_bucket = "medium"
    else:
        null_bucket = "high"

    return {
        "normalized_column_name": normalized,
        "inferred_dtype": dtype,
        "null_rate": null_value,
        "null_rate_bucket": null_bucket,
        "candidate_bucket": candidate_bucket,
        "is_placeholder_column": is_placeholder,
        "is_string_like_dtype": is_string_like_dtype,
        "has_text_name_signal": has_text_name_signal,
        "is_candidate_text": is_text,
        "is_candidate_id_or_code": is_id and not is_placeholder,
        "is_candidate_site": is_site and not is_placeholder,
        "is_candidate_asset": is_asset and not is_placeholder,
        "is_candidate_date": is_date and not is_placeholder,
        "is_catalog_signal": is_catalog_signal and not is_placeholder,
    }


def runtime_likelihood(likely_role: str) -> str:
    if likely_role in RUNTIME_SOURCE_ROLES:
        return "potential_runtime_or_source_signal"
    if likely_role in REFERENCE_ROLES:
        return "analysis_mapping_or_reference_only"
    return "unclear"


def profile_schema() -> dict[str, Any]:
    structural_rows = read_csv(STRUCTURAL_SCAN_PATH)
    internal_rows: list[dict[str, Any]] = []
    sanitized_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for scan_row in structural_rows:
        if scan_row.get("scan_kind") != "tabular" or scan_row.get("read_status") != "read_ok":
            continue

        column_names = safe_json_loads(scan_row.get("column_names_json", ""), [])
        inferred_dtypes = safe_json_loads(scan_row.get("inferred_dtypes_json", ""), {})
        null_rates = safe_json_loads(scan_row.get("null_rates_json", ""), {})
        sheet_hash = scan_row.get("sheet_hash", "")
        path_hash = scan_row.get("path_hash", "")
        likely_role = scan_row.get("likely_role", "unknown")
        runtime_bucket = runtime_likelihood(likely_role)

        for position, column_name in enumerate(column_names):
            column_name = str(column_name)
            dtype = str(inferred_dtypes.get(column_name, "unknown"))
            null_rate = null_rates.get(column_name)
            profile = infer_column_profile(column_name, dtype, null_rate)
            column_hash = stable_hash(f"{path_hash}::{sheet_hash}::{position}::{profile['normalized_column_name']}")

            common = {
                "package_id": scan_row.get("package_id", ""),
                "path_hash": path_hash,
                "sheet_hash": sheet_hash,
                "column_hash": column_hash,
                "extension": scan_row.get("extension", ""),
                "likely_role": likely_role,
                "data_family": scan_row.get("data_family", ""),
                "runtime_likelihood": runtime_bucket,
                "row_count_estimate": scan_row.get("row_count_estimate", ""),
                "sampled_row_count": scan_row.get("sampled_row_count", ""),
                "column_position": position,
                **{key: value for key, value in profile.items() if key != "normalized_column_name"},
            }
            internal = {
                **common,
                "relative_path": scan_row.get("relative_path", ""),
                "file_name": scan_row.get("file_name", ""),
                "sheet_name": scan_row.get("sheet_name", ""),
                "column_name": column_name,
                "normalized_column_name": profile["normalized_column_name"],
            }
            sanitized = common.copy()
            internal_rows.append(internal)
            sanitized_rows.append(sanitized)
            if profile["candidate_bucket"] != "other" or profile["is_catalog_signal"]:
                candidate_rows.append(internal)

    internal_path = INTERNAL_REPORTS_DIR / "schema_profile.csv"
    sanitized_path = REPORTS_DIR / "schema_profile_sanitized.csv"
    candidate_internal_path = INTERNAL_REPORTS_DIR / "candidate_schema_columns.csv"
    candidate_sanitized_path = REPORTS_DIR / "candidate_schema_columns_sanitized.csv"

    write_csv(internal_path, internal_rows)
    write_csv(sanitized_path, sanitized_rows)
    write_csv(candidate_internal_path, candidate_rows)
    write_csv(candidate_sanitized_path, [
        {key: value for key, value in row.items() if key not in {"relative_path", "file_name", "sheet_name", "column_name", "normalized_column_name"}}
        for row in candidate_rows
    ])

    summary = {
        "created_at_utc": now_utc(),
        "input_structural_scan": str(STRUCTURAL_SCAN_PATH.relative_to(PROJECT_ROOT)),
        "tabular_sheet_rows_scanned": len({(row.get("path_hash"), row.get("sheet_hash")) for row in structural_rows if row.get("scan_kind") == "tabular" and row.get("read_status") == "read_ok"}),
        "schema_column_count": len(internal_rows),
        "candidate_column_count": len(candidate_rows),
        "candidate_bucket_counts": dict(Counter(str(row["candidate_bucket"]) for row in internal_rows)),
        "runtime_likelihood_counts": dict(Counter(str(row["runtime_likelihood"]) for row in internal_rows)),
        "likely_role_counts": dict(Counter(str(row["likely_role"]) for row in internal_rows)),
        "null_rate_bucket_counts": dict(Counter(str(row["null_rate_bucket"]) for row in internal_rows)),
        "catalog_signal_column_count": sum(1 for row in internal_rows if row["is_catalog_signal"]),
        "outputs": {
            "sanitized_schema_profile_path": str(sanitized_path.relative_to(PROJECT_ROOT)),
            "sanitized_candidate_columns_path": str(candidate_sanitized_path.relative_to(PROJECT_ROOT)),
            "internal_schema_profile_path": str(internal_path.relative_to(PROJECT_ROOT)),
            "internal_candidate_columns_path": str(candidate_internal_path.relative_to(PROJECT_ROOT)),
        },
        "raw_operational_values_emitted": False,
    }
    internal_summary_path = INTERNAL_ARTIFACTS_DIR / "schema_profile_summary.json"
    sanitized_summary_path = ARTIFACTS_DIR / "schema_profile_summary_sanitized.json"
    internal_summary_path.parent.mkdir(parents=True, exist_ok=True)
    sanitized_summary_path.parent.mkdir(parents=True, exist_ok=True)
    internal_summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    sanitized_summary = {key: value for key, value in summary.items() if key != "outputs"}
    sanitized_summary["outputs"] = {
        "sanitized_schema_profile_path": str(sanitized_path.relative_to(PROJECT_ROOT)),
        "sanitized_candidate_columns_path": str(candidate_sanitized_path.relative_to(PROJECT_ROOT)),
    }
    sanitized_summary_path.write_text(json.dumps(sanitized_summary, indent=2), encoding="utf-8")
    return summary
