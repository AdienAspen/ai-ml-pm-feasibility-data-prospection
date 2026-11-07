from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_PACKAGE_DIR = PROJECT_ROOT / "data" / "raw" / "source_package"
EXTRACTED_DIR = PROJECT_ROOT / "data" / "interim" / "extracted_source"
REPORTS_DIR = PROJECT_ROOT / "reports"
INTERNAL_REPORTS_DIR = REPORTS_DIR / "internal"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
INTERNAL_ARTIFACTS_DIR = ARTIFACTS_DIR / "internal"

SUPPORTED_ARCHIVES = {".zip"}
TABULAR_EXTENSIONS = {".csv", ".tsv", ".xls", ".xlsx"}
STRUCTURED_EXTENSIONS = {".json", ".xml"}
DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md", ".msg"}


@dataclass(frozen=True)
class InventoryRow:
    package_id: str
    path_hash: str
    relative_path: str
    file_name: str
    extension: str
    size_bytes: int
    likely_role: str
    data_family: str
    is_tabular: bool
    is_structured: bool
    is_document: bool


@dataclass(frozen=True)
class SanitizedInventoryRow:
    package_id: str
    path_hash: str
    extension: str
    size_bytes: int
    likely_role: str
    data_family: str
    is_tabular: bool
    is_structured: bool
    is_document: bool


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_hash(value: str, length: int = 16) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:length]


def ensure_dirs() -> None:
    for path in [EXTRACTED_DIR, REPORTS_DIR, INTERNAL_REPORTS_DIR, ARTIFACTS_DIR, INTERNAL_ARTIFACTS_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def list_archives(raw_dir: Path = RAW_PACKAGE_DIR) -> list[Path]:
    return sorted(path for path in raw_dir.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED_ARCHIVES)


def package_id_for_archive(archive_path: Path, index: int) -> str:
    return f"package_{index:03d}_{stable_hash(archive_path.name, 8)}"


def safe_extract_zip(zip_path: Path, destination: Path, force: bool = False) -> list[str]:
    if force and destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True, exist_ok=True)

    extracted: list[str] = []
    destination_resolved = destination.resolve()
    with zipfile.ZipFile(zip_path) as archive:
        for member in archive.infolist():
            member_path = destination / member.filename
            resolved = member_path.resolve()
            if destination_resolved not in resolved.parents and resolved != destination_resolved:
                raise ValueError(f"Unsafe archive member path: {member.filename}")
            archive.extract(member, destination)
            if not member.is_dir():
                extracted.append(member.filename)
    return extracted


def infer_role(relative_path: str, extension: str) -> str:
    lowered = relative_path.lower()
    if any(token in lowered for token in ["mapping", "map", "instruction", "guide", "guidance"]):
        return "mapping_doc"
    if any(token in lowered for token in ["catalog", "code", "reference", "matrix", "equipment", "functional_location"]):
        return "reference_data"
    if extension in TABULAR_EXTENSIONS | STRUCTURED_EXTENSIONS | {".pdf"}:
        return "source_data"
    return "unknown"


def infer_family(extension: str) -> str:
    if extension in TABULAR_EXTENSIONS:
        return "tabular"
    if extension in STRUCTURED_EXTENSIONS:
        return "structured"
    if extension in DOCUMENT_EXTENSIONS:
        return "document"
    return "other"


def iter_files(base_dir: Path) -> Iterable[Path]:
    return sorted(path for path in base_dir.rglob("*") if path.is_file())


def build_inventory(force_extract: bool = False) -> tuple[list[InventoryRow], dict]:
    ensure_dirs()
    archives = list_archives()
    extraction_summary = []

    for index, archive_path in enumerate(archives, start=1):
        package_id = package_id_for_archive(archive_path, index)
        package_dir = EXTRACTED_DIR / package_id
        extracted_files = safe_extract_zip(archive_path, package_dir, force=force_extract)
        extraction_summary.append(
            {
                "package_id": package_id,
                "archive_hash": stable_hash(archive_path.name),
                "archive_size_bytes": archive_path.stat().st_size,
                "extracted_file_count": len(extracted_files),
            }
        )

    rows: list[InventoryRow] = []
    for package_dir in sorted(path for path in EXTRACTED_DIR.iterdir() if path.is_dir()):
        package_id = package_dir.name
        for file_path in iter_files(package_dir):
            relative_path = file_path.relative_to(package_dir).as_posix()
            extension = file_path.suffix.lower()
            row = InventoryRow(
                package_id=package_id,
                path_hash=stable_hash(f"{package_id}/{relative_path}"),
                relative_path=relative_path,
                file_name=file_path.name,
                extension=extension or "[no_extension]",
                size_bytes=file_path.stat().st_size,
                likely_role=infer_role(relative_path, extension),
                data_family=infer_family(extension),
                is_tabular=extension in TABULAR_EXTENSIONS,
                is_structured=extension in STRUCTURED_EXTENSIONS,
                is_document=extension in DOCUMENT_EXTENSIONS,
            )
            rows.append(row)

    summary = {
        "created_at_utc": utc_now(),
        "raw_operational_values_emitted": False,
        "archive_count": len(archives),
        "extracted_package_count": len(extraction_summary),
        "file_count": len(rows),
        "internal_inventory_path": "reports/internal/source_file_inventory.csv",
        "sanitized_inventory_path": "reports/source_file_inventory_sanitized.csv",
        "extraction_summary": extraction_summary,
        "counts_by_family": count_by(rows, "data_family"),
        "counts_by_role": count_by(rows, "likely_role"),
        "counts_by_extension": count_by(rows, "extension"),
    }
    return rows, summary


def count_by(rows: list[InventoryRow], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(getattr(row, field))
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_inventory_outputs(rows: list[InventoryRow], summary: dict) -> dict[str, str]:
    internal_rows = [asdict(row) for row in rows]
    sanitized_rows = [
        asdict(
            SanitizedInventoryRow(
                package_id=row.package_id,
                path_hash=row.path_hash,
                extension=row.extension,
                size_bytes=row.size_bytes,
                likely_role=row.likely_role,
                data_family=row.data_family,
                is_tabular=row.is_tabular,
                is_structured=row.is_structured,
                is_document=row.is_document,
            )
        )
        for row in rows
    ]

    internal_inventory_path = INTERNAL_REPORTS_DIR / "source_file_inventory.csv"
    sanitized_inventory_path = REPORTS_DIR / "source_file_inventory_sanitized.csv"
    internal_summary_path = INTERNAL_ARTIFACTS_DIR / "source_inventory_summary.json"
    sanitized_summary_path = ARTIFACTS_DIR / "source_inventory_summary_sanitized.json"

    write_csv(internal_inventory_path, internal_rows)
    write_csv(sanitized_inventory_path, sanitized_rows)
    internal_summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    sanitized_summary = dict(summary)
    sanitized_summary["extraction_summary"] = [
        {
            "package_id": item["package_id"],
            "archive_hash": item["archive_hash"],
            "archive_size_bytes": item["archive_size_bytes"],
            "extracted_file_count": item["extracted_file_count"],
        }
        for item in summary["extraction_summary"]
    ]
    sanitized_summary_path.write_text(json.dumps(sanitized_summary, indent=2), encoding="utf-8")

    return {
        "internal_inventory_path": str(internal_inventory_path),
        "sanitized_inventory_path": str(sanitized_inventory_path),
        "internal_summary_path": str(internal_summary_path),
        "sanitized_summary_path": str(sanitized_summary_path),
    }
