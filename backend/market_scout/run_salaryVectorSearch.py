from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.repositories import SalaryVectorRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search salary job records with Firestore vector search.")
    parser.add_argument("--query", required=True, help="User salary benchmark query.")
    parser.add_argument("--top-k", type=int, default=10, help="Number of filtered results to return.")
    parser.add_argument("--fetch-k", type=int, default=None, help="Number of vector results to fetch before filtering.")
    parser.add_argument("--distance-threshold", type=float, default=None, help="Optional vector distance threshold.")
    parser.add_argument("--no-location-filter", action="store_true", help="Do not post-filter by extracted location.")
    parser.add_argument("--no-experience-filter", action="store_true", help="Do not post-filter by extracted experience.")
    parser.add_argument("--include-missing-salary", action="store_true", help="Include records without salary.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repository = SalaryVectorRepository()
    results = repository.search(
        args.query,
        top_k=args.top_k,
        fetch_k=args.fetch_k,
        require_salary=not args.include_missing_salary,
        filter_location=not args.no_location_filter,
        filter_experience=not args.no_experience_filter,
        distance_threshold=args.distance_threshold,
    )

    print(
        json.dumps(
            {
                "query": args.query,
                "result_count": len(results),
                "results": [result.to_dict() for result in results],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
