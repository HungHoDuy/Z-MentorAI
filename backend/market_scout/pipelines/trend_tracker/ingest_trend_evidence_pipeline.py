from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.market_scout.repositories.salary_benchmark.salary_repository import (
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.repositories.trend_tracker.trend_evidence_repository import (
    DEFAULT_TREND_EVIDENCE_COLLECTION,
    DEFAULT_TREND_SOURCE_COLLECTION,
)
from backend.market_scout.schemas.trend_tracker.trend_external_evidence import TrendEvidence, TrendSource


@dataclass(frozen=True)
class IngestTrendEvidenceResult:
    source_collection: str
    evidence_collection: str
    source_records: int
    evidence_records: int
    written_source_records: int
    written_evidence_records: int
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "success",
            "source_collection": self.source_collection,
            "evidence_collection": self.evidence_collection,
            "source_records": self.source_records,
            "evidence_records": self.evidence_records,
            "written_source_records": self.written_source_records,
            "written_evidence_records": self.written_evidence_records,
            "dry_run": self.dry_run,
        }


class IngestTrendEvidencePipeline:
    """Persist manually reviewed sources and claims for external outlook retrieval."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        source_collection: str | None = None,
        evidence_collection: str | None = None,
    ) -> None:
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.source_collection = source_collection or env_or_default(
            "MARKET_SCOUT_TREND_SOURCE_COLLECTION", DEFAULT_TREND_SOURCE_COLLECTION
        )
        self.evidence_collection = evidence_collection or env_or_default(
            "MARKET_SCOUT_TREND_EVIDENCE_COLLECTION", DEFAULT_TREND_EVIDENCE_COLLECTION
        )

    def run(
        self,
        *,
        sources: list[TrendSource],
        evidence: list[TrendEvidence],
        dry_run: bool = False,
    ) -> IngestTrendEvidenceResult:
        _validate_payload(sources, evidence)
        if not dry_run:
            batch = self.firestore_client.batch()
            source_ref = self.firestore_client.collection(self.source_collection)
            evidence_ref = self.firestore_client.collection(self.evidence_collection)
            for record in sources:
                batch.set(source_ref.document(record.source_id), trend_source_to_document(record), merge=True)
            for record in evidence:
                batch.set(evidence_ref.document(record.evidence_id), trend_evidence_to_document(record), merge=True)
            batch.commit()
        return IngestTrendEvidenceResult(
            source_collection=self.source_collection,
            evidence_collection=self.evidence_collection,
            source_records=len(sources),
            evidence_records=len(evidence),
            written_source_records=0 if dry_run else len(sources),
            written_evidence_records=0 if dry_run else len(evidence),
            dry_run=dry_run,
        )


def trend_source_to_document(source: TrendSource) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "source_name": source.source_name,
        "publisher": source.publisher,
        "source_type": source.source_type,
        "published_at": source.published_at.isoformat(),
        "fetched_at": source.fetched_at.isoformat(),
        "reliability_score": source.reliability_score,
        "scope_location_ids": list(source.scope_location_ids),
        "scope_period": source.scope_period,
        "url": source.url,
        "content_hash": source.content_hash,
        "notes": source.notes,
        "schema_version": 1,
    }


def trend_evidence_to_document(evidence: TrendEvidence) -> dict[str, Any]:
    return {
        "evidence_id": evidence.evidence_id,
        "source_id": evidence.source_id,
        "job_family_ids": list(evidence.job_family_ids),
        "job_category_ids": list(evidence.job_category_ids),
        "location_ids": list(evidence.location_ids),
        "period": evidence.period,
        "direction": evidence.direction,
        "exact_claim": evidence.exact_claim,
        "metric_value": evidence.metric_value,
        "metric_unit": evidence.metric_unit,
        "citation": evidence.citation,
        "confidence": evidence.confidence,
        "schema_version": 1,
    }


def _validate_payload(sources: list[TrendSource], evidence: list[TrendEvidence]) -> None:
    source_ids = [source.source_id for source in sources]
    evidence_ids = [claim.evidence_id for claim in evidence]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Duplicate source_id values are not allowed.")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("Duplicate evidence_id values are not allowed.")
    unknown_sources = {claim.source_id for claim in evidence} - set(source_ids)
    if unknown_sources:
        raise ValueError(f"Evidence references unknown source ids: {sorted(unknown_sources)}")
