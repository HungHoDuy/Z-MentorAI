from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.pipelines.salary_benchmark.embed_firestore_jobs_pipeline import EmbedFirestoreJobsPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed Firestore job documents into a vector-search collection.")
    parser.add_argument("--source-collection", default=None, help="Firestore collection that stores cleaned job data.")
    parser.add_argument("--vector-collection", default=None, help="Firestore collection that stores embedded job data.")
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for testing on a small sample.")
    parser.add_argument("--batch-size", type=int, default=10, help="Embedding/write batch size.")
    parser.add_argument("--page-size", type=int, default=100, help="Firestore read page size.")
    parser.add_argument("--stream-timeout", type=int, default=60, help="Firestore stream timeout per page in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Build embedding text without generating or writing vectors.")
    parser.add_argument("--include-missing-salary", action="store_true", help="Also embed documents without salary fields.")
    parser.add_argument("--verbose", action="store_true", help="Print progress logs while running.")
    parser.add_argument("--log-file", default=None, help="Optional path to write progress logs.")
    return parser.parse_args()


def configure_logging(verbose: bool, log_file: str | None) -> logging.Logger:
    logger = logging.getLogger("backend.market_scout.pipelines.embed_firestore_jobs_pipeline")
    logger.setLevel(logging.INFO if verbose or log_file else logging.WARNING)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    if verbose:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def main() -> None:
    args = parse_args()
    logger = configure_logging(args.verbose, args.log_file)
    pipeline = EmbedFirestoreJobsPipeline(
        source_collection=args.source_collection,
        vector_collection=args.vector_collection,
        batch_size=args.batch_size,
        page_size=args.page_size,
        stream_timeout=args.stream_timeout,
        logger=logger,
    )
    result = pipeline.run(
        limit=args.limit,
        dry_run=args.dry_run,
        require_salary=not args.include_missing_salary,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
