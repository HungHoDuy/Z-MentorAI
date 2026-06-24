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

from backend.market_scout.pipelines.build_job_family_trend_snapshots_pipeline import (
    BuildJobFamilyTrendSnapshotsPipeline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build weekly job-family-by-location trend snapshots from v2 facts."
    )
    parser.add_argument("--period-start", required=True, type=_parse_date, help="Inclusive period start in YYYY-MM-DD.")
    parser.add_argument("--period-end", required=True, type=_parse_date, help="Inclusive period end in YYYY-MM-DD.")
    parser.add_argument("--period", default=None, help="Optional snapshot label; defaults to the ISO week of period end.")
    parser.add_argument("--facts-collection", default=None, help="Source Firestore collection; defaults to trend_job_facts_v2.")
    parser.add_argument("--snapshots-collection", default=None, help="Target Firestore collection; defaults to trend_snapshots_v2.")
    parser.add_argument("--limit", type=int, default=None, help="Optional source-document limit for a small test run.")
    parser.add_argument("--page-size", type=int, default=500, help="Firestore read page size.")
    parser.add_argument("--batch-size", type=int, default=400, help="Firestore write batch size, maximum 500.")
    parser.add_argument("--dry-run", action="store_true", help="Build snapshots without writing Firestore documents.")
    parser.add_argument("--verbose", action="store_true", help="Print pipeline progress logs.")
    return parser.parse_args()


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected YYYY-MM-DD.") from exc


def configure_logging(verbose: bool) -> logging.Logger:
    logger = logging.getLogger(
        "backend.market_scout.pipelines.build_job_family_trend_snapshots_pipeline"
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
    pipeline = BuildJobFamilyTrendSnapshotsPipeline(
        fact_collection=args.facts_collection,
        snapshot_collection=args.snapshots_collection,
        page_size=args.page_size,
        batch_size=args.batch_size,
        logger=configure_logging(args.verbose),
    )
    result = pipeline.run(
        period_start=args.period_start,
        period_end=args.period_end,
        period=args.period,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
