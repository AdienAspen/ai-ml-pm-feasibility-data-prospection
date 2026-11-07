from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from asset_ml_feasibility.evidence.pair_evidence_classification import (
    run_pair_evidence_classification,
)


def main() -> int:
    summary = run_pair_evidence_classification()
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
