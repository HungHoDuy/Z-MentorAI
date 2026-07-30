from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.pipelines.trend_tracker.embed_job_mapping_pipeline import EmbedJobMappingPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Embed trend job facts into job_mapping_embedding.")
    parser.add_argument("--source-collection", default=None, help="Source trend job fact collection.")
    parser.add_argument("--embedding-collection", default=None, help="Target embedding collection.")
    parser.add_argument(
        "--source-collection-filter",
        default=None,
        help="Optional filter for trend fact source_collection, e.g. data_for_vectorize_2026W31.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional limit for testing.")
    parser.add_argument("--batch-size", type=int, default=10, help="Embedding/write batch size.")
    parser.add_argument("--page-size", type=int, default=100, help="Firestore read page size.")
    parser.add_argument("--stream-timeout", type=int, default=60, help="Firestore stream timeout per page in seconds.")
    parser.add_argument("--dry-run", action="store_true", help="Build documents without calling embedding service or writing vectors.")
    parser.add_argument("--verbose", action="store_true", help="Print progress logs.")
    return parser.parse_args()


def configure_logging(verbose: bool) -> logging.Logger:
    logger = logging.getLogger("backend.market_scout.pipelines.trend_tracker.embed_job_mapping_pipeline")
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
    pipeline = EmbedJobMappingPipeline(
        source_collection=args.source_collection,
        embedding_collection=args.embedding_collection,
        source_collection_filter=args.source_collection_filter,
        batch_size=args.batch_size,
        page_size=args.page_size,
        stream_timeout=args.stream_timeout,
        logger=configure_logging(args.verbose),
    )
    result = pipeline.run(limit=args.limit, dry_run=args.dry_run)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()