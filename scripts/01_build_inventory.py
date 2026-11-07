from __future__ import annotations

import argparse
import json
from pathlib import Path

from asset_ml_feasibility.ingest.inventory import build_inventory, write_inventory_outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build sanitized and internal source-file inventory from local source packages."
    )
    parser.add_argument(
        "--force-extract",
        action="store_true",
        help="Recreate extracted working folders before inventorying source packages.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows, summary = build_inventory(force_extract=args.force_extract)
    output_paths = write_inventory_outputs(rows, summary)
    result = {
        "file_count": summary["file_count"],
        "archive_count": summary["archive_count"],
        "counts_by_family": summary["counts_by_family"],
        "counts_by_role": summary["counts_by_role"],
        "outputs": output_paths,
        "raw_operational_values_emitted": False,
    }
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
