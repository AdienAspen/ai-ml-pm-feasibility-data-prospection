from __future__ import annotations

import importlib.util
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_MODULES = [
    "pandas",
    "openpyxl",
    "pdfplumber",
    "lxml",
    "sklearn",
    "spacy",
]


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    internal_result = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "modules": {name: module_available(name) for name in REQUIRED_MODULES},
        "raw_operational_values_emitted": False,
    }

    output_path = project_root / "artifacts" / "internal" / "environment_check_summary.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(internal_result, indent=2), encoding="utf-8")

    public_result = dict(internal_result)
    public_result["project_root"] = "[internal_path]"
    public_result["python_executable"] = Path(sys.executable).name
    public_result["internal_summary_path"] = "artifacts/internal/environment_check_summary.json"
    print(json.dumps(public_result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
