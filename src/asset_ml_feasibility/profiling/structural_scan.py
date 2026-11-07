from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIR = PROJECT_ROOT / "reports"
INTERNAL_REPORTS_DIR = REPORTS_DIR / "internal"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INTERNAL_ARTIFACTS_DIR = ARTIFACTS_DIR / "internal"
INVENTORY_PATH = INTERNAL_REPORTS_DIR / "source_file_inventory.csv"
EXTRACTED_SOURCE_DIR = PROJECT_ROOT / "data" / "interim" / "extracted_source"

TABULAR_EXTENSIONS = {".csv", ".tsv", ".xls", ".xlsx"}
STRUCTURED_EXTENSIONS = {".json", ".xml"}
SAMPLE_ROWS = 200


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()[:16]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_inventory() -> list[dict[str, str]]:
    with INVENTORY_PATH.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def resolve_internal_path(row: dict[str, str]) -> Path:
    relative_path = row["relative_path"]
    package_id = row.get("package_id", "")
    if package_id:
        return EXTRACTED_SOURCE_DIR / package_id / relative_path
    return PROJECT_ROOT / relative_path


def classify_error(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "password" in message or "encrypted" in message:
        return "encrypted_or_protected"
    if "no such file" in message or "not found" in message:
        return "missing_file"
    if "empty" in message or "no columns" in message:
        return "empty_sheet_or_file"
    if "unsupported" in message or "format" in message:
        return "unsupported_format"
    if "permission" in message:
        return "unreadable_file"
    if "badzip" in name or "zip" in message:
        return "invalid_archive_or_workbook"
    return "parser_issue"


def estimate_delimited_rows(path: Path) -> int | None:
    try:
        with path.open("rb") as handle:
            return max(sum(1 for _ in handle) - 1, 0)
    except OSError:
        return None


def scan_delimited(path: Path, delimiter: str) -> list[dict[str, Any]]:
    sample = pd.read_csv(path, sep=delimiter, nrows=SAMPLE_ROWS, dtype="object", encoding_errors="replace")
    row_count = estimate_delimited_rows(path)
    return [
        {
            "sheet_name": "[delimited]",
            "row_count_estimate": row_count,
            "sampled_row_count": int(len(sample)),
            "column_count": int(len(sample.columns)),
            "column_names": list(map(str, sample.columns)),
            "inferred_dtypes": {str(col): str(dtype) for col, dtype in sample.dtypes.items()},
            "null_rates": {str(col): float(sample[col].isna().mean()) if len(sample) else None for col in sample.columns},
        }
    ]


def scan_excel(path: Path) -> list[dict[str, Any]]:
    excel = pd.ExcelFile(path)
    outputs: list[dict[str, Any]] = []
    for sheet in excel.sheet_names:
        sample = pd.read_excel(path, sheet_name=sheet, nrows=SAMPLE_ROWS, dtype="object")
        row_count = None
        try:
            if path.suffix.lower() == ".xlsx":
                from openpyxl import load_workbook

                workbook = load_workbook(path, read_only=True, data_only=True)
                if sheet in workbook.sheetnames:
                    row_count = max((workbook[sheet].max_row or 1) - 1, 0)
                workbook.close()
        except Exception:
            row_count = None
        outputs.append(
            {
                "sheet_name": str(sheet),
                "row_count_estimate": row_count,
                "sampled_row_count": int(len(sample)),
                "column_count": int(len(sample.columns)),
                "column_names": list(map(str, sample.columns)),
                "inferred_dtypes": {str(col): str(dtype) for col, dtype in sample.dtypes.items()},
                "null_rates": {str(col): float(sample[col].isna().mean()) if len(sample) else None for col in sample.columns},
            }
        )
    return outputs


def scan_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        keys = list(payload.keys())
        record_count = len(payload)
        top_type = "object"
    elif isinstance(payload, list):
        keys = list(payload[0].keys()) if payload and isinstance(payload[0], dict) else []
        record_count = len(payload)
        top_type = "array"
    else:
        keys = []
        record_count = 1
        top_type = type(payload).__name__
    return {"top_type": top_type, "top_keys": keys, "record_count_estimate": record_count}


def scan_xml(path: Path) -> dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    child_tags = [child.tag.split("}")[-1] for child in list(root)[:1000]]
    return {
        "root_tag": root.tag.split("}")[-1],
        "top_child_tags": sorted(set(child_tags)),
        "record_count_estimate": len(list(root)),
    }


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


def scan_structures() -> dict[str, Any]:
    inventory = read_inventory()
    internal_rows: list[dict[str, Any]] = []
    sanitized_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []
    status_counter: Counter[str] = Counter()
    family_counter: Counter[str] = Counter()
    role_counter: Counter[str] = Counter()

    for row in inventory:
        extension = row["extension"].lower()
        if extension not in TABULAR_EXTENSIONS and extension not in STRUCTURED_EXTENSIONS:
            continue

        path = resolve_internal_path(row)
        base = {
            "package_id": row["package_id"],
            "path_hash": row["path_hash"],
            "extension": extension,
            "likely_role": row["likely_role"],
            "data_family": row["data_family"],
            "size_bytes": int(row["size_bytes"] or 0),
        }
        family_counter[row["data_family"]] += 1
        role_counter[row["likely_role"]] += 1

        try:
            if extension == ".csv":
                sheet_outputs = scan_delimited(path, ",")
                scan_kind = "tabular"
            elif extension == ".tsv":
                sheet_outputs = scan_delimited(path, "\t")
                scan_kind = "tabular"
            elif extension in {".xls", ".xlsx"}:
                sheet_outputs = scan_excel(path)
                scan_kind = "tabular"
            elif extension == ".json":
                structured = scan_json(path)
                internal_rows.append({**base, **structured, "relative_path": row["relative_path"], "file_name": row["file_name"], "read_status": "read_ok", "scan_kind": "structured"})
                sanitized_rows.append({**base, "read_status": "read_ok", "scan_kind": "structured", "record_count_estimate": structured["record_count_estimate"], "top_key_or_tag_count": len(structured.get("top_keys", []))})
                status_counter["read_ok"] += 1
                continue
            else:
                structured = scan_xml(path)
                internal_rows.append({**base, **structured, "relative_path": row["relative_path"], "file_name": row["file_name"], "read_status": "read_ok", "scan_kind": "structured"})
                sanitized_rows.append({**base, "read_status": "read_ok", "scan_kind": "structured", "record_count_estimate": structured["record_count_estimate"], "top_key_or_tag_count": len(structured.get("top_child_tags", []))})
                status_counter["read_ok"] += 1
                continue

            for sheet in sheet_outputs:
                sheet_hash = stable_hash(f"{row['path_hash']}::{sheet['sheet_name']}")
                internal_rows.append(
                    {
                        **base,
                        "relative_path": row["relative_path"],
                        "file_name": row["file_name"],
                        "sheet_name": sheet["sheet_name"],
                        "sheet_hash": sheet_hash,
                        "read_status": "read_ok",
                        "scan_kind": scan_kind,
                        "row_count_estimate": sheet["row_count_estimate"],
                        "sampled_row_count": sheet["sampled_row_count"],
                        "column_count": sheet["column_count"],
                        "column_names_json": json.dumps(sheet["column_names"], ensure_ascii=False),
                        "inferred_dtypes_json": json.dumps(sheet["inferred_dtypes"], ensure_ascii=False),
                        "null_rates_json": json.dumps(sheet["null_rates"], ensure_ascii=False),
                    }
                )
                sanitized_rows.append(
                    {
                        **base,
                        "sheet_hash": sheet_hash,
                        "read_status": "read_ok",
                        "scan_kind": scan_kind,
                        "row_count_estimate": sheet["row_count_estimate"],
                        "sampled_row_count": sheet["sampled_row_count"],
                        "column_count": sheet["column_count"],
                    }
                )
                status_counter["read_ok"] += 1
        except Exception as exc:
            error_category = classify_error(exc)
            error_rows.append(
                {
                    **base,
                    "relative_path": row["relative_path"],
                    "file_name": row["file_name"],
                    "read_status": "read_error",
                    "error_category": error_category,
                    "error_type": type(exc).__name__,
                    "error_message": str(exc)[:500],
                }
            )
            sanitized_rows.append(
                {
                    **base,
                    "read_status": "read_error",
                    "scan_kind": "unknown",
                    "error_category": error_category,
                    "row_count_estimate": None,
                    "sampled_row_count": None,
                    "column_count": None,
                }
            )
            status_counter[f"error:{error_category}"] += 1

    internal_scan_path = INTERNAL_REPORTS_DIR / "basic_structural_scan.csv"
    sanitized_scan_path = REPORTS_DIR / "basic_structural_scan_sanitized.csv"
    internal_error_path = INTERNAL_REPORTS_DIR / "basic_structural_scan_errors.csv"
    internal_summary_path = INTERNAL_ARTIFACTS_DIR / "basic_structural_scan_summary.json"
    sanitized_summary_path = ARTIFACTS_DIR / "basic_structural_scan_summary_sanitized.json"

    write_csv(internal_scan_path, internal_rows)
    write_csv(sanitized_scan_path, sanitized_rows)
    write_csv(internal_error_path, error_rows)

    summary = {
        "created_at_utc": now_utc(),
        "input_inventory": "reports/internal/source_file_inventory.csv",
        "files_attempted": sum(family_counter.values()),
        "output_rows": len(sanitized_rows),
        "read_status_counts": dict(sorted(status_counter.items())),
        "attempted_by_family": dict(sorted(family_counter.items())),
        "attempted_by_role": dict(sorted(role_counter.items())),
        "outputs": {
            "sanitized_scan_path": "reports/basic_structural_scan_sanitized.csv",
            "internal_scan_path": "reports/internal/basic_structural_scan.csv",
            "internal_error_path": "reports/internal/basic_structural_scan_errors.csv",
        },
        "raw_operational_values_emitted": False,
    }
    internal_summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    sanitized_summary = {
        key: value
        for key, value in summary.items()
        if key not in {"outputs"}
    }
    sanitized_summary["outputs"] = {"sanitized_scan_path": "reports/basic_structural_scan_sanitized.csv"}
    sanitized_summary_path.write_text(json.dumps(sanitized_summary, indent=2), encoding="utf-8")
    return summary
