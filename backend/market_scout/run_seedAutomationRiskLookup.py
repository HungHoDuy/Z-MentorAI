from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.pipelines.seed_automation_risk_lookup_pipeline import (
    SeedAutomationRiskLookupPipeline,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the curated automation-exposure MVP lookup.")
    parser.add_argument("--collection", help="Firestore collection name.")
    parser.add_argument("--dry-run", action="store_true", help="Validate the seed without writing Firestore.")
    args = parser.parse_args()

    result = SeedAutomationRiskLookupPipeline(collection_name=args.collection).run(dry_run=args.dry_run)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
