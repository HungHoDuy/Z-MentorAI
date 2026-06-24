from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.market_scout.pipelines.ingest_trend_evidence_pipeline import (
    IngestTrendEvidencePipeline,
)
from backend.market_scout.repositories.trend_tracker.trend_evidence_repository import (
    trend_evidence_from_document,
    trend_source_from_document,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest manually reviewed external trend evidence.")
    parser.add_argument("--input", required=True, help="JSON file containing sources and evidence arrays.")
    parser.add_argument("--sources-collection", default=None, help="Target source collection.")
    parser.add_argument("--evidence-collection", default=None, help="Target evidence collection.")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing Firestore.")
    args = parser.parse_args()

    payload = _load_payload(Path(args.input))
    sources = []
    for index, document in enumerate(payload["sources"]):
        source = trend_source_from_document(f"source-{index}", document)
        if source is None:
            raise ValueError(f"Invalid source record at sources[{index}].")
        sources.append(source)

    evidence = []
    for index, document in enumerate(payload["evidence"]):
        claim = trend_evidence_from_document(f"evidence-{index}", document)
        if claim is None:
            raise ValueError(f"Invalid evidence record at evidence[{index}].")
        evidence.append(claim)

    result = IngestTrendEvidencePipeline(
        source_collection=args.sources_collection,
        evidence_collection=args.evidence_collection,
    ).run(sources=sources, evidence=evidence, dry_run=args.dry_run)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))


def _load_payload(path: Path) -> dict[str, list[dict[str, Any]]]:
    with path.open(encoding="utf-8") as input_file:
        payload = json.load(input_file)
    if not isinstance(payload, dict):
        raise ValueError("Input must be a JSON object.")
    sources = payload.get("sources")
    evidence = payload.get("evidence")
    if not isinstance(sources, list) or not isinstance(evidence, list):
        raise ValueError("Input must contain sources and evidence arrays.")
    if not all(isinstance(record, dict) for record in [*sources, *evidence]):
        raise ValueError("All source and evidence records must be JSON objects.")
    return {"sources": sources, "evidence": evidence}


if __name__ == "__main__":
    main()
