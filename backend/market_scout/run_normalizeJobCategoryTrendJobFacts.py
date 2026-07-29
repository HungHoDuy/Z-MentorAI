from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.pipelines.trend_tracker.normalize_job_category_trend_job_facts_pipeline import (
    NormalizeJobCategoryTrendJobFactsPipeline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize raw Firestore jobs into JobCategoryTaxonomy-backed trend facts."
    )
    parser.add_argument("--source-collection", default=None, help="Raw Firestore job collection; defaults to data_for_vectorize.")
    parser.add_argument("--facts-collection", default=None, help="Target Firestore collection; defaults to trend_job_facts_v2.")
    parser.add_argument("--observed-at", type=_parse_date, default=None, help="Date used to evaluate expiry, YYYY-MM-DD.")
    parser.add_argument("--limit", type=int, default=None, help="Optional source-document limit for small test runs.")
    parser.add_argument("--page-size", type=int, default=500, help="Firestore read page size.")
    parser.add_argument("--batch-size", type=int, default=400, help="Firestore write batch size, maximum 500.")
    parser.add_argument("--dry-run", action="store_true", help="Normalize documents without writing Firestore facts.")
    parser.add_argument("--verbose", action="store_true", help="Print pipeline progress logs.")
    return parser.parse_args()


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected YYYY-MM-DD.") from exc


def configure_logging(verbose: bool) -> logging.Logger:
    logger = logging.getLogger(
        "backend.market_scout.pipelines.trend_tracker.normalize_job_category_trend_job_facts_pipeline"
    )
    logger.setLevel(logging.INFO if verbose else logging.WARNING)
    logger.handlers.clear()
    logger.propagate = False
    if verbose:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def main() -> None:
    args = parse_args()
    pipeline = NormalizeJobCategoryTrendJobFactsPipeline(
        source_collection=args.source_collection,
        fact_collection=args.facts_collection,
        page_size=args.page_size,
        batch_size=args.batch_size,
        logger=configure_logging(args.verbose),
    )
    result = pipeline.run(
        limit=args.limit,
        observed_at=args.observed_at,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
