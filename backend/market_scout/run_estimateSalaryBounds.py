from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.pipelines.estimate_salary_bounds_pipeline import EstimateSalaryBoundsPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Estimate open-ended salary bounds in Firestore.")
    parser.add_argument("--collection", default=None, help="Collection to update. Defaults to MARKET_SCOUT_VECTOR_COLLECTION.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for testing.")
    parser.add_argument("--batch-size", type=int, default=400, help="Firestore write batch size.")
    parser.add_argument("--page-size", type=int, default=500, help="Firestore read page size.")
    parser.add_argument("--stream-timeout", type=int, default=60, help="Firestore stream timeout per page.")
    parser.add_argument("--dry-run", action="store_true", help="Calculate updates without writing to Firestore.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pipeline = EstimateSalaryBoundsPipeline(
        collection_name=args.collection,
        batch_size=args.batch_size,
        page_size=args.page_size,
        stream_timeout=args.stream_timeout,
    )
    result = pipeline.run(limit=args.limit, dry_run=args.dry_run)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
