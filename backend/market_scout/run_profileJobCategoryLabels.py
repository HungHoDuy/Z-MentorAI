from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.pipelines.profile_job_category_labels_pipeline import (
    ProfileJobCategoryLabelsPipeline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Profile CareerViet job-category labels against JobCategoryTaxonomy v1."
    )
    parser.add_argument("--source-collection", default=None, help="Raw Firestore job collection.")
    parser.add_argument("--limit", type=int, default=None, help="Optional source-document limit.")
    parser.add_argument("--top-k", type=int, default=100, help="Number of most frequent labels to return.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = ProfileJobCategoryLabelsPipeline(source_collection=args.source_collection).run(
        limit=args.limit,
        top_k=args.top_k,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
