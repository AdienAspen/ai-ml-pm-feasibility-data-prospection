from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = PROJECT_ROOT / "reports"
INTERNAL_REPORTS_DIR = REPORTS_DIR / "internal"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INTERNAL_ARTIFACTS_DIR = ARTIFACTS_DIR / "internal"
INVENTORY_PATH = INTERNAL_REPORTS_DIR / "source_file_inventory.csv"
EXTRACTED_ROOT = PROJECT_ROOT / "data" / "interim" / "extracted_source"

CATALOG_TARGET_BY_SHEET_TOKEN = {
    "catalog_s": "Symptom",
    "catalog_b": "Object Part",
    "catalog_c": "Damage",
    "catalog_5": "Cause",
    "catalog_a": "Activity",
}

TARGET_BY_CATALOG_CODE = {
    "S": "Symptom",
    "B": "Object Part",
    "C": "Damage",
    "5": "Cause",
    "A": "Activity",
}

CATALOG_COLUMN_HINTS = {
    "catalog": ("catalog", "catalogue"),
    "code_group": ("code_group", "code group", "group"),
    "code": ("code",),
    "description": ("short_text", "short text", "description", "desc", "text"),
}

REFERENCE_ROLES = {"reference_data", "mapping_doc"}
TABULAR_EXTENSIONS = {".csv", ".xlsx", ".xls", ".xlsm"}


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


def normalize_name(value: Any) -> str:
    value = "" if value is None else str(value)
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


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


def classify_reference_file(relative_path: str, file_name: str) -> str:
    normalized = normalize_name(f"{relative_path} {file_name}")
    if "catalog" in normalized and "code" in normalized:
        return "master_catalog"
    if "canonical_field_matrix" in normalized or "field_matrix" in normalized:
        return "field_matrix"
    if "mapping" in normalized or "odata" in normalized:
        return "mapping_reference"
    if "equipment" in normalized or "functional_location" in normalized or "historical_orders" in normalized:
        return "operational_reference"
    return "other_reference"


def resolve_source_path(package_id: str, relative_path: str) -> Path:
    direct = EXTRACTED_ROOT / package_id / relative_path
    if direct.exists():
        return direct

    matches = [candidate for candidate in EXTRACTED_ROOT.glob(f"*/{relative_path}") if candidate.is_file()]
    if len(matches) == 1:
        return matches[0]

    return direct


def read_tabular_file(path: Path) -> dict[str, pd.DataFrame]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return {"__csv__": pd.read_csv(path, dtype=str, nrows=5000)}
    if suffix in {".xlsx", ".xls", ".xlsm"}:
        excel = pd.ExcelFile(path)
        return {sheet: pd.read_excel(excel, sheet_name=sheet, dtype=str, nrows=5000) for sheet in excel.sheet_names}
    return {}


def find_column(columns: list[str], hints: tuple[str, ...]) -> str | None:
    normalized_columns = [(column, normalize_name(column)) for column in columns]
    normalized_hints = [normalize_name(hint) for hint in hints]
    for column, normalized in normalized_columns:
        if any(hint == normalized for hint in normalized_hints):
            return column
    for column, normalized in normalized_columns:
        if any(hint in normalized for hint in normalized_hints):
            return column
    return None


def infer_target(sheet_name: str, catalog_value: Any) -> str:
    normalized_sheet = normalize_name(sheet_name)
    for token, target in CATALOG_TARGET_BY_SHEET_TOKEN.items():
        if token in normalized_sheet:
            return target
    catalog_code = str(catalog_value or "").strip().upper()
    return TARGET_BY_CATALOG_CODE.get(catalog_code, "unknown")


def row_value(row: pd.Series, column: str | None) -> str:
    if not column:
        return ""
    value = row.get(column, "")
    if isinstance(value, pd.Series):
        non_empty = [item for item in value.tolist() if str(item).strip() and str(item).strip().lower() != "nan"]
        value = non_empty[0] if non_empty else ""
    return str(value or "").strip()


def extract_catalog_terms(df: pd.DataFrame, sheet_name: str, source_id: str, source_file: str) -> list[dict[str, Any]]:
    columns = [str(column) for column in df.columns]
    catalog_col = find_column(columns, CATALOG_COLUMN_HINTS["catalog"])
    code_group_col = find_column(columns, CATALOG_COLUMN_HINTS["code_group"])
    code_col = find_column(columns, CATALOG_COLUMN_HINTS["code"])
    desc_col = find_column(columns, CATALOG_COLUMN_HINTS["description"])
    if not code_col or not desc_col:
        return []

    rows: list[dict[str, Any]] = []
    useful = df[[col for col in [catalog_col, code_group_col, code_col, desc_col] if col]].dropna(how="all")
    for idx, row in useful.iterrows():
        code = row_value(row, code_col)
        description = row_value(row, desc_col)
        if not code or not description or code.lower() == "nan" or description.lower() == "nan":
            continue
        catalog_value = row_value(row, catalog_col)
        code_group = row_value(row, code_group_col)
        target = infer_target(sheet_name, catalog_value)
        term_id = stable_hash(f"{source_id}|{sheet_name}|{idx}|{catalog_value}|{code_group}|{code}|{description}")
        rows.append(
            {
                "term_id": term_id,
                "target": target,
                "catalog": str(catalog_value or "").strip(),
                "code_group": code_group,
                "code": code,
                "official_description": description,
                "normalized_description": normalize_name(description),
                "source_id": source_id,
                "source_file": source_file,
                "sheet_name": sheet_name,
                "source_type": "master_catalog_term",
            }
        )
    return rows


def load_catalog_references() -> dict[str, Any]:
    inventory_rows = read_csv(INVENTORY_PATH)
    reference_rows = [
        row for row in inventory_rows
        if row.get("likely_role") in REFERENCE_ROLES and row.get("extension", "").lower() in TABULAR_EXTENSIONS
    ]

    internal_sources: list[dict[str, Any]] = []
    sanitized_sources: list[dict[str, Any]] = []
    internal_terms: list[dict[str, Any]] = []
    sanitized_terms: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for row in reference_rows:
        relative_path = row.get("relative_path", "")
        file_name = row.get("file_name", "")
        file_path = resolve_source_path(row.get("package_id", ""), relative_path)
        source_id = stable_hash(relative_path)
        reference_type = classify_reference_file(relative_path, file_name)
        source_common = {
            "source_id": source_id,
            "extension": row.get("extension", ""),
            "likely_role": row.get("likely_role", ""),
            "data_family": row.get("data_family", ""),
            "reference_type": reference_type,
        }
        internal_sources.append({**source_common, "relative_path": relative_path, "file_name": file_name})
        sanitized_sources.append(source_common)

        try:
            sheets = read_tabular_file(file_path)
        except Exception as exc:  # noqa: BLE001
            errors.append({"source_id": source_id, "reference_type": reference_type, "error_type": type(exc).__name__, "error_message": str(exc)[:200]})
            continue

        if reference_type == "master_catalog":
            for sheet_name, df in sheets.items():
                terms = extract_catalog_terms(df, sheet_name, source_id, file_name)
                internal_terms.extend(terms)
                for term in terms:
                    sanitized_terms.append(
                        {
                            "term_id": term["term_id"],
                            "target": term["target"],
                            "catalog_hash": stable_hash(term["catalog"]),
                            "code_group_hash": stable_hash(term["code_group"]),
                            "code_hash": stable_hash(term["code"]),
                            "description_hash": stable_hash(term["official_description"]),
                            "normalized_description_hash": stable_hash(term["normalized_description"]),
                            "source_id": term["source_id"],
                            "sheet_hash": stable_hash(term["sheet_name"]),
                            "source_type": term["source_type"],
                        }
                    )

    INTERNAL_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    INTERNAL_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    write_csv(INTERNAL_REPORTS_DIR / "catalog_reference_sources.csv", internal_sources)
    write_csv(REPORTS_DIR / "catalog_reference_sources_sanitized.csv", sanitized_sources)
    write_csv(INTERNAL_REPORTS_DIR / "catalog_vocabulary_terms.csv", internal_terms)
    write_csv(REPORTS_DIR / "catalog_vocabulary_terms_sanitized.csv", sanitized_terms)
    write_csv(INTERNAL_REPORTS_DIR / "catalog_loading_errors.csv", errors)

    summary = {
        "created_at_utc": now_utc(),
        "reference_tabular_sources": len(reference_rows),
        "reference_type_counts": dict(Counter(row["reference_type"] for row in internal_sources)),
        "catalog_term_count": len(internal_terms),
        "catalog_terms_by_target": dict(Counter(row["target"] for row in internal_terms)),
        "catalog_loading_error_count": len(errors),
        "outputs": {
            "sanitized_sources_path": "reports/catalog_reference_sources_sanitized.csv",
            "sanitized_terms_path": "reports/catalog_vocabulary_terms_sanitized.csv",
            "internal_sources_path": "reports/internal/catalog_reference_sources.csv",
            "internal_terms_path": "reports/internal/catalog_vocabulary_terms.csv",
            "internal_errors_path": "reports/internal/catalog_loading_errors.csv",
        },
        "raw_operational_values_emitted": False,
    }
    (INTERNAL_ARTIFACTS_DIR / "catalog_loading_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (ARTIFACTS_DIR / "catalog_loading_summary_sanitized.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
