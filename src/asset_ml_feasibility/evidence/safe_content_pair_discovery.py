from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "data" / "interim" / "extracted_source"
REPORTS_DIR = PROJECT_ROOT / "reports"
INTERNAL_REPORTS_DIR = REPORTS_DIR / "internal"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INTERNAL_ARTIFACTS_DIR = ARTIFACTS_DIR / "internal"

INVENTORY_PATH = INTERNAL_REPORTS_DIR / "source_file_inventory.csv"
SCHEMA_PROFILE_PATH = INTERNAL_REPORTS_DIR / "schema_profile.csv"
TARGET_MAPPING_PATH = INTERNAL_REPORTS_DIR / "preliminary_target_mapping.csv"

INTERNAL_PAIR_DISCOVERY_PATH = INTERNAL_REPORTS_DIR / "safe_content_pair_discovery.csv"
SANITIZED_PAIR_DISCOVERY_PATH = REPORTS_DIR / "safe_content_pair_discovery_sanitized.csv"
INTERNAL_ERROR_PATH = INTERNAL_REPORTS_DIR / "safe_content_pair_discovery_errors.csv"
SANITIZED_SUMMARY_PATH = ARTIFACTS_DIR / "safe_content_pair_discovery_summary_sanitized.json"
INTERNAL_SUMMARY_PATH = INTERNAL_ARTIFACTS_DIR / "safe_content_pair_discovery_summary.json"

TARGET_ORDER = [
    "Symptom",
    "Object Part",
    "Damage",
    "Cause",
    "Activity",
    "FLOC leaf segment",
    "Activity Type",
]

TEXT_NAME_HINTS = {
    "text",
    "description",
    "desc",
    "note",
    "notes",
    "comment",
    "comments",
    "reason",
    "summary",
    "name",
    "problem",
    "event",
    "activity",
    "action",
    "work",
    "failure",
    "fault",
}

CODE_NAME_HINTS = {
    "code",
    "catalog",
    "group",
    "type",
    "id",
    "key",
    "number",
    "num",
    "status",
    "state",
    "fault",
    "activitytype",
    "activity_type",
}

MAX_CELL_LENGTH_FOR_PROFILE = 500
MAX_STRUCTURED_RECORDS = 2000


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


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


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def normalized_name(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


def source_path(package_id: str, relative_path: str) -> Path:
    return DATA_ROOT / package_id / relative_path


def safe_text_series(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().str.slice(0, MAX_CELL_LENGTH_FOR_PROFILE)


def is_non_empty(series: pd.Series) -> pd.Series:
    text = safe_text_series(series)
    lowered = text.str.lower()
    return (text != "") & ~lowered.isin({"nan", "none", "null", "nat", "no data available"})


def looks_text_like(series: pd.Series, column_name: str) -> bool:
    name = normalized_name(column_name)
    if any(hint in name for hint in TEXT_NAME_HINTS):
        return True
    text = safe_text_series(series)
    non_empty = text[text != ""]
    if non_empty.empty:
        return False
    avg_len = non_empty.str.len().mean()
    alpha_rate = non_empty.str.contains(r"[A-Za-z]", regex=True).mean()
    return bool(avg_len >= 12 and alpha_rate >= 0.5)


def looks_code_like(series: pd.Series, column_name: str) -> bool:
    name = normalized_name(column_name)
    if any(hint in name for hint in CODE_NAME_HINTS):
        return True
    text = safe_text_series(series)
    non_empty = text[text != ""]
    if non_empty.empty:
        return False
    avg_len = non_empty.str.len().mean()
    cardinality_rate = non_empty.nunique(dropna=True) / max(len(non_empty), 1)
    shortish_rate = (non_empty.str.len() <= 24).mean()
    return bool(avg_len <= 24 and shortish_rate >= 0.75 and cardinality_rate <= 0.8)


def schema_candidates(schema: pd.DataFrame, path_hash: str, sheet_hash: str) -> tuple[list[str], list[str]]:
    if schema.empty:
        return [], []
    sheet_schema = schema[(schema["path_hash"] == path_hash) & (schema["sheet_hash"] == sheet_hash)]
    if sheet_schema.empty:
        return [], []
    sheet_schema = sheet_schema[~sheet_schema.get("is_placeholder_column", False).map(as_bool)]
    text_cols = sheet_schema[sheet_schema["is_candidate_text"].map(as_bool)]["column_name"].dropna().astype(str).tolist()
    code_cols = sheet_schema[
        sheet_schema["is_candidate_id_or_code"].map(as_bool) | sheet_schema["is_catalog_signal"].map(as_bool)
    ]["column_name"].dropna().astype(str).tolist()
    return list(dict.fromkeys(text_cols)), list(dict.fromkeys(code_cols))


def target_hints(target_mapping: pd.DataFrame, path_hash: str, sheet_hash: str) -> list[str]:
    if target_mapping.empty:
        return []
    subset = target_mapping[(target_mapping["path_hash"] == path_hash) & (target_mapping["sheet_hash"] == sheet_hash)]
    targets = [target for target in subset.get("target", pd.Series(dtype=str)).dropna().astype(str).unique() if target]
    ordered = [target for target in TARGET_ORDER if target in set(targets)]
    extras = sorted(set(targets) - set(ordered))
    return ordered + extras


def profile_pair(
    df: pd.DataFrame,
    *,
    text_col: str,
    code_col: str,
) -> dict[str, Any]:
    text_non_empty = is_non_empty(df[text_col])
    code_non_empty = is_non_empty(df[code_col])
    cooccur = text_non_empty & code_non_empty
    code_values = safe_text_series(df.loc[code_non_empty, code_col])
    text_values = safe_text_series(df.loc[text_non_empty, text_col])
    return {
        "row_count": int(len(df)),
        "text_non_empty_rows": int(text_non_empty.sum()),
        "code_non_empty_rows": int(code_non_empty.sum()),
        "cooccurring_rows": int(cooccur.sum()),
        "cooccurrence_rate": float(cooccur.sum() / max(len(df), 1)),
        "code_distinct_count": int(code_values.nunique(dropna=True)),
        "text_distinct_count": int(text_values.nunique(dropna=True)),
        "mean_text_length": float(text_values.str.len().mean()) if len(text_values) else 0.0,
        "mean_code_length": float(code_values.str.len().mean()) if len(code_values) else 0.0,
    }


def read_tabular_file(path: Path, extension: str, sheet_name: str | None = None) -> dict[str, pd.DataFrame]:
    if extension in {".xlsx", ".xls"}:
        if not sheet_name:
            return pd.read_excel(path, sheet_name=None, dtype=object)
        return {sheet_name: pd.read_excel(path, sheet_name=sheet_name, dtype=object)}
    if extension in {".csv", ".tsv"}:
        sep = "\t" if extension == ".tsv" else ","
        return {"": pd.read_csv(path, sep=sep, dtype=object, low_memory=False)}
    return {}


def flatten_json_records(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, dict):
        for item in value.values():
            if isinstance(item, list) and item and all(isinstance(row, dict) for row in item[:10]):
                return [row for row in item if isinstance(row, dict)]
        return [value]
    return []


def read_structured_file(path: Path, extension: str) -> pd.DataFrame:
    if extension == ".json":
        value = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
        records = flatten_json_records(value)[:MAX_STRUCTURED_RECORDS]
        return pd.json_normalize(records, sep=".") if records else pd.DataFrame()
    if extension == ".xml":
        root = ET.parse(path).getroot()
        records: list[dict[str, Any]] = []
        for child in list(root)[:MAX_STRUCTURED_RECORDS]:
            row: dict[str, Any] = {"tag": child.tag}
            row.update({f"attr_{key}": val for key, val in child.attrib.items()})
            for grandchild in list(child):
                text = (grandchild.text or "").strip()
                if text:
                    row[grandchild.tag] = text
                for key, val in grandchild.attrib.items():
                    row[f"{grandchild.tag}_attr_{key}"] = val
            records.append(row)
        return pd.DataFrame(records)
    return pd.DataFrame()


def discover_pairs_for_dataframe(
    df: pd.DataFrame,
    *,
    package_id: str,
    path_hash: str,
    sheet_hash: str,
    extension: str,
    data_family: str,
    likely_role: str,
    relative_path: str,
    file_name: str,
    sheet_name: str,
    schema: pd.DataFrame,
    target_mapping: pd.DataFrame,
) -> list[dict[str, Any]]:
    if df.empty:
        return []

    schema_text_cols, schema_code_cols = schema_candidates(schema, path_hash, sheet_hash)
    columns = [str(col) for col in df.columns]
    text_cols = [col for col in schema_text_cols if col in df.columns]
    code_cols = [col for col in schema_code_cols if col in df.columns]

    if not text_cols:
        text_cols = [col for col in columns if looks_text_like(df[col], col)]
    if not code_cols:
        code_cols = [col for col in columns if looks_code_like(df[col], col)]

    text_cols = list(dict.fromkeys(text_cols))[:8]
    code_cols = list(dict.fromkeys([col for col in code_cols if col not in text_cols]))[:12]
    hints = target_hints(target_mapping, path_hash, sheet_hash)
    target_hint = ";".join(hints) if hints else "unknown"

    rows: list[dict[str, Any]] = []
    for text_col in text_cols:
        for code_col in code_cols:
            metrics = profile_pair(df, text_col=text_col, code_col=code_col)
            if metrics["cooccurring_rows"] <= 0:
                continue
            pair_hash = stable_hash(f"{path_hash}|{sheet_hash}|{text_col}|{code_col}")
            rows.append(
                {
                    "package_id": package_id,
                    "path_hash": path_hash,
                    "sheet_hash": sheet_hash,
                    "pair_hash": pair_hash,
                    "extension": extension,
                    "data_family": data_family,
                    "likely_role": likely_role,
                    "target_hint": target_hint,
                    "target_hint_count": len(hints),
                    "text_column_hash": stable_hash(text_col),
                    "code_column_hash": stable_hash(code_col),
                    "text_column_name": text_col,
                    "code_column_name": code_col,
                    "row_count": metrics["row_count"],
                    "text_non_empty_rows": metrics["text_non_empty_rows"],
                    "code_non_empty_rows": metrics["code_non_empty_rows"],
                    "cooccurring_rows": metrics["cooccurring_rows"],
                    "cooccurrence_rate": round(metrics["cooccurrence_rate"], 6),
                    "code_distinct_count": metrics["code_distinct_count"],
                    "text_distinct_count": metrics["text_distinct_count"],
                    "mean_text_length": round(metrics["mean_text_length"], 3),
                    "mean_code_length": round(metrics["mean_code_length"], 3),
                    "pair_evidence_type": "text_code_cooccurrence_candidate",
                    "can_support_measurement": False,
                    "needs_runtime_validation": True,
                    "needs_label_validation": True,
                    "row_level_validation_performed": False,
                    "raw_operational_values_emitted": False,
                    "relative_path": relative_path,
                    "file_name": file_name,
                    "sheet_name": sheet_name,
                }
            )
    return rows


def sanitized_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    safe_keys = [
        "package_id",
        "path_hash",
        "sheet_hash",
        "pair_hash",
        "extension",
        "data_family",
        "likely_role",
        "target_hint",
        "target_hint_count",
        "text_column_hash",
        "code_column_hash",
        "row_count",
        "text_non_empty_rows",
        "code_non_empty_rows",
        "cooccurring_rows",
        "cooccurrence_rate",
        "code_distinct_count",
        "text_distinct_count",
        "mean_text_length",
        "mean_code_length",
        "pair_evidence_type",
        "can_support_measurement",
        "needs_runtime_validation",
        "needs_label_validation",
        "row_level_validation_performed",
        "raw_operational_values_emitted",
    ]
    return [{key: row.get(key, "") for key in safe_keys} for row in rows]


def run_safe_content_pair_discovery() -> dict[str, Any]:
    inventory = read_csv_if_present(INVENTORY_PATH)
    schema = read_csv_if_present(SCHEMA_PROFILE_PATH)
    target_mapping = read_csv_if_present(TARGET_MAPPING_PATH)

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if inventory.empty:
        summary = {
            "created_at_utc": now_utc(),
            "input_files": 0,
            "files_attempted": 0,
            "files_read_ok": 0,
            "pair_candidate_rows": 0,
            "error_count": 0,
            "raw_operational_values_emitted": False,
        }
        INTERNAL_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        SANITIZED_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        INTERNAL_SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        SANITIZED_SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    source_files = inventory[
        (inventory["likely_role"].fillna("") == "source_data")
        & (inventory["data_family"].isin(["tabular", "structured"]))
    ].copy()

    files_attempted = 0
    files_read_ok = 0
    sheet_read_ok = 0
    for _, file_row in source_files.iterrows():
        package_id = str(file_row.get("package_id", ""))
        relative_path = str(file_row.get("relative_path", ""))
        extension = str(file_row.get("extension", "")).lower()
        data_family = str(file_row.get("data_family", ""))
        likely_role = str(file_row.get("likely_role", ""))
        path_hash = str(file_row.get("path_hash", ""))
        file_name = str(file_row.get("file_name", ""))
        path = source_path(package_id, relative_path)
        files_attempted += 1
        try:
            if data_family == "tabular":
                sheet_schema = schema[schema["path_hash"] == path_hash] if not schema.empty else pd.DataFrame()
                sheet_names = list(sheet_schema.get("sheet_name", pd.Series(dtype=str)).dropna().astype(str).unique())
                if not sheet_names:
                    sheet_names = [None]
                file_rows_before = len(rows)
                for sheet_name in sheet_names:
                    sheets = read_tabular_file(path, extension, sheet_name if sheet_name else None)
                    for actual_sheet_name, df in sheets.items():
                        sheet_hash = stable_hash(f"{path_hash}|{actual_sheet_name}")
                        if not sheet_schema.empty:
                            matched = sheet_schema[sheet_schema["sheet_name"].fillna("").astype(str) == str(actual_sheet_name)]
                            if not matched.empty:
                                sheet_hash = str(matched.iloc[0].get("sheet_hash", sheet_hash))
                        rows.extend(
                            discover_pairs_for_dataframe(
                                df,
                                package_id=package_id,
                                path_hash=path_hash,
                                sheet_hash=sheet_hash,
                                extension=extension,
                                data_family=data_family,
                                likely_role=likely_role,
                                relative_path=relative_path,
                                file_name=file_name,
                                sheet_name=str(actual_sheet_name),
                                schema=schema,
                                target_mapping=target_mapping,
                            )
                        )
                        sheet_read_ok += 1
                files_read_ok += 1
                if len(rows) == file_rows_before:
                    pass
            elif data_family == "structured":
                df = read_structured_file(path, extension)
                rows.extend(
                    discover_pairs_for_dataframe(
                        df,
                        package_id=package_id,
                        path_hash=path_hash,
                        sheet_hash=stable_hash(f"{path_hash}|structured"),
                        extension=extension,
                        data_family=data_family,
                        likely_role=likely_role,
                        relative_path=relative_path,
                        file_name=file_name,
                        sheet_name="structured_records",
                        schema=schema,
                        target_mapping=target_mapping,
                    )
                )
                files_read_ok += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "package_id": package_id,
                    "path_hash": path_hash,
                    "extension": extension,
                    "data_family": data_family,
                    "likely_role": likely_role,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:300],
                    "relative_path": relative_path,
                    "file_name": file_name,
                    "raw_operational_values_emitted": False,
                }
            )

    internal_rows = sorted(rows, key=lambda row: (-int(row.get("cooccurring_rows", 0)), row.get("target_hint", "")))
    safe_rows = sanitized_rows(internal_rows)

    write_csv(INTERNAL_PAIR_DISCOVERY_PATH, internal_rows)
    write_csv(SANITIZED_PAIR_DISCOVERY_PATH, safe_rows)
    write_csv(INTERNAL_ERROR_PATH, errors)

    target_counter = Counter(row.get("target_hint", "unknown") for row in internal_rows)
    family_counter = Counter(row.get("data_family", "unknown") for row in internal_rows)
    summary = {
        "created_at_utc": now_utc(),
        "input_source_files": int(len(source_files)),
        "files_attempted": int(files_attempted),
        "files_read_ok": int(files_read_ok),
        "sheet_or_record_groups_read_ok": int(sheet_read_ok),
        "pair_candidate_rows": int(len(internal_rows)),
        "distinct_files_with_pairs": int(len({row.get("path_hash") for row in internal_rows})),
        "distinct_pair_hashes": int(len({row.get("pair_hash") for row in internal_rows})),
        "cooccurring_row_total": int(sum(int(row.get("cooccurring_rows", 0)) for row in internal_rows)),
        "pair_rows_by_target_hint": dict(sorted(target_counter.items())),
        "pair_rows_by_data_family": dict(sorted(family_counter.items())),
        "error_count": int(len(errors)),
        "settings": {
            "method_scope": "safe_content_text_code_pair_discovery_for_tabular_and_structured_source_data",
            "documents_and_pdfs_attempted": False,
            "row_level_validation_performed": False,
            "can_support_measurement_without_validation": False,
            "raw_values_emitted_in_versionable_outputs": False,
        },
        "outputs": {
            "internal_pair_discovery_csv": str(INTERNAL_PAIR_DISCOVERY_PATH.relative_to(PROJECT_ROOT)),
            "sanitized_pair_discovery_csv": str(SANITIZED_PAIR_DISCOVERY_PATH.relative_to(PROJECT_ROOT)),
            "internal_error_csv": str(INTERNAL_ERROR_PATH.relative_to(PROJECT_ROOT)),
        },
        "raw_operational_values_emitted": False,
    }

    INTERNAL_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SANITIZED_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    INTERNAL_SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    SANITIZED_SUMMARY_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
