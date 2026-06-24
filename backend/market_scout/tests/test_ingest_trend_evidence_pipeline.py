from datetime import date

import pytest

from backend.market_scout.pipelines.ingest_trend_evidence_pipeline import (
    IngestTrendEvidencePipeline,
    trend_evidence_to_document,
    trend_source_to_document,
)
from backend.market_scout.schemas.trend_external_evidence import TrendEvidence, TrendSource


def test_pipeline_dry_run_validates_claim_source_relationship() -> None:
    source = _source()
    claim = _evidence(source.source_id)

    result = IngestTrendEvidencePipeline(
        firestore_client=object(),
    ).run(sources=[source], evidence=[claim], dry_run=True)

    assert result.source_records == 1
    assert result.evidence_records == 1
    assert result.written_evidence_records == 0


def test_pipeline_rejects_claim_with_unknown_source() -> None:
    with pytest.raises(ValueError, match="unknown source"):
        IngestTrendEvidencePipeline(firestore_client=object()).run(
            sources=[], evidence=[_evidence("missing-source")], dry_run=True
        )


def test_document_serializers_keep_citation_and_source_scope() -> None:
    source = _source()
    evidence = _evidence(source.source_id)

    assert trend_source_to_document(source)["scope_location_ids"] == ["ha-noi"]
    assert trend_evidence_to_document(evidence)["citation"] == "Page 12"


def _source() -> TrendSource:
    return TrendSource(
        source_id="source-1",
        source_name="Verified report",
        publisher="Publisher",
        source_type="labor_market_report",
        published_at=date(2026, 6, 1),
        fetched_at=date(2026, 6, 20),
        reliability_score=0.8,
        scope_location_ids=["ha-noi"],
        scope_period="2026-Q2",
        url="https://example.com/report",
        content_hash=None,
        notes=None,
    )


def _evidence(source_id: str) -> TrendEvidence:
    return TrendEvidence(
        evidence_id="evidence-1",
        source_id=source_id,
        job_family_ids=["finance_legal"],
        job_category_ids=["accounting_audit"],
        location_ids=["ha-noi"],
        period="2026-Q2",
        direction="increase",
        exact_claim="A reviewed claim.",
        metric_value=18,
        metric_unit="percent_qoq",
        citation="Page 12",
        confidence="medium",
    )
