from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.repositories import SalaryVectorRepository
from backend.market_scout.services.salary_benchmark_service import SalaryBenchmarkService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run salary benchmark from Firestore vector search results.")
    parser.add_argument("--query", required=True, help="User salary benchmark query.")
    parser.add_argument("--top-k", type=int, default=30, help="Final number of vector matches to aggregate.")
    parser.add_argument("--fetch-k", type=int, default=80, help="Vector results to fetch before post-filtering.")
    parser.add_argument("--distance-threshold", type=float, default=None, help="Optional vector distance threshold.")
    parser.add_argument("--no-location-filter", action="store_true", help="Do not post-filter by extracted location.")
    parser.add_argument("--no-experience-filter", action="store_true", help="Do not post-filter by extracted experience.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    vector_repository = SalaryVectorRepository()
    benchmark_service = SalaryBenchmarkService()

    search_results = vector_repository.search(
        args.query,
        top_k=args.top_k,
        fetch_k=args.fetch_k,
        require_salary=True,
        filter_location=not args.no_location_filter,
        filter_experience=not args.no_experience_filter,
        distance_threshold=args.distance_threshold,
    )
    benchmark = benchmark_service.aggregate(args.query, search_results)

    print(
        json.dumps(
            {
                "query": args.query,
                "retrieved_records": len(search_results),
                "benchmark": benchmark.to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
