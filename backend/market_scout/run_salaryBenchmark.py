from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.flows import SalaryBenchmarkFlow
from backend.market_scout.services import SalarySummaryService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run salary benchmark from Firestore vector search results.")
    parser.add_argument("--query", required=True, help="User salary benchmark query.")
    parser.add_argument("--top-k", type=int, default=30, help="Final number of vector matches to aggregate.")
    parser.add_argument("--fetch-k", type=int, default=80, help="Vector results to fetch before post-filtering.")
    parser.add_argument("--distance-threshold", type=float, default=None, help="Optional vector distance threshold.")
    parser.add_argument("--no-location-filter", action="store_true", help="Do not post-filter by extracted location.")
    parser.add_argument("--no-experience-filter", action="store_true", help="Do not post-filter by extracted experience.")
    parser.add_argument("--llm-model", default=None, help="Vertex AI chat model used to summarize the result.")
    parser.add_argument("--llm-temperature", type=float, default=None, help="LLM temperature.")
    parser.add_argument("--llm-max-output-tokens", type=int, default=None, help="LLM max output tokens.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summary_service = SalarySummaryService(
        model_name=args.llm_model,
        temperature=args.llm_temperature,
        max_output_tokens=args.llm_max_output_tokens,
    )
    flow = SalaryBenchmarkFlow(summary_service=summary_service)
    result = flow.run(
        args.query,
        top_k=args.top_k,
        fetch_k=args.fetch_k,
        filter_location=not args.no_location_filter,
        filter_experience=not args.no_experience_filter,
        distance_threshold=args.distance_threshold,
    )

    print(
        json.dumps(
            result.to_dict(),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
