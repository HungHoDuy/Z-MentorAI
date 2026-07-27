from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.pipelines.trend_tracker.ingest_external_outlook_sources_pipeline import (
    DEFAULT_EXTERNAL_OUTLOOK_CONFIG_PATH,
    IngestExternalOutlookSourcesPipeline,
    load_external_outlook_source_configs,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch allowlisted external outlook sources into trend_sources.")
    parser.add_argument("--config", default=str(DEFAULT_EXTERNAL_OUTLOOK_CONFIG_PATH), help="Allowlist JSON path.")
    parser.add_argument("--sources-collection", default=None, help="Target trend source collection.")
    parser.add_argument("--evidence-collection", default=None, help="Target trend evidence collection.")
    parser.add_argument("--extract-evidence", action="store_true", help="Use LLM to extract structured evidence claims.")
    parser.add_argument("--timeout-seconds", type=int, default=30, help="HTTP fetch timeout per source.")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without writing Firestore.")
    parser.add_argument("--verbose", action="store_true", help="Enable detailed logs.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    source_configs = load_external_outlook_source_configs(Path(args.config))
    logging.info("Loaded %s external outlook sources from %s", len(source_configs), args.config)
    for source in source_configs:
        logging.info("Configured source: %s %s", source.source_id, source.url)

    result = IngestExternalOutlookSourcesPipeline(
        source_collection=args.sources_collection,
        evidence_collection=args.evidence_collection,
        fetch_timeout_seconds=args.timeout_seconds,
    ).run(
        source_configs=source_configs,
        dry_run=args.dry_run,
        extract_evidence=args.extract_evidence,
    )

    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
