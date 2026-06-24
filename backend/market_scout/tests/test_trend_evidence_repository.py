from datetime import date

from backend.market_scout.repositories.trend_evidence_repository import (
    select_external_outlook_evidence,
    trend_evidence_from_document,
    trend_source_from_document,
)
from backend.market_scout.schemas.trend_external_evidence import (
    TrendEvidence,
    TrendEvidenceMatch,
    TrendSource,
)


def test_select_external_outlook_requires_exact_family_and_location_scope() -> None:
    eligible = _match(source_location="ha-noi", evidence_location="ha-noi", published_at=date(2026, 6, 1))
    wrong_source_scope = _match(source_location="ho-chi-minh", evidence_location="ha-noi", published_at=date(2026, 6, 2))
    wrong_evidence_scope = _match(source_location="ha-noi", evidence_location="ho-chi-minh", published_at=date(2026, 6, 3))

    results = select_external_outlook_evidence(
        [eligible, wrong_source_scope, wrong_evidence_scope],
        job_family_id="finance_legal",
        location_id="ha-noi",
        published_after=date(2026, 5, 1),
        min_reliability_score=0.7,
        limit=10,
    )

    assert results == [eligible]


def test_select_external_outlook_filters_age_and_reliability_then_sorts_newest_first() -> None:
    recent = _match(source_location="ha-noi", evidence_location="ha-noi", published_at=date(2026, 6, 10))
    old = _match(source_location="ha-noi", evidence_location="ha-noi", published_at=date(2026, 4, 1))
    low_reliability = _match(
        source_location="ha-noi", evidence_location="ha-noi", published_at=date(2026, 6, 20), reliability=0.6
    )

    results = select_external_outlook_evidence(
        [old, low_reliability, recent],
        job_family_id="finance_legal",
        location_id="ha-noi",
        published_after=date(2026, 5, 1),
        min_reliability_score=0.7,
        limit=10,
    )

    assert results == [recent]


def test_document_parsers_require_claim_citation_and_source_scope() -> None:
    source = trend_source_from_document(
        "source-1",
        {
            "source_id": "source-1",
            "source_name": "Verified report",
            "publisher": "Publisher",
            "source_type": "labor_market_report",
            "published_at": "2026-06-01",
            "fetched_at": "2026-06-20",
            "reliability_score": 0.8,
            "scope_location_ids": ["ha-noi"],
            "url": "https://example.com/report",
        },
    )
    evidence = trend_evidence_from_document(
        "evidence-1",
        {
            "evidence_id": "evidence-1",
            "source_id": "source-1",
            "job_family_ids": ["finance_legal"],
            "location_ids": ["ha-noi"],
            "direction": "increase",
            "exact_claim": "A reviewed claim.",
            "citation": "Page 12",
            "confidence": "medium",
        },
    )

    assert source is not None
    assert evidence is not None


def _match(
    *,
    source_location: str,
    evidence_location: str,
    published_at: date,
    reliability: float = 0.8,
) -> TrendEvidenceMatch:
    return TrendEvidenceMatch(
        source=TrendSource(
            source_id=f"source-{source_location}-{evidence_location}-{published_at}",
            source_name="Verified report",
            publisher="Publisher",
            source_type="labor_market_report",
            published_at=published_at,
            fetched_at=date(2026, 6, 20),
            reliability_score=reliability,
            scope_location_ids=[source_location],
            scope_period="2026-Q2",
            url="https://example.com/report",
            content_hash=None,
            notes=None,
        ),
        evidence=TrendEvidence(
            evidence_id=f"evidence-{source_location}-{evidence_location}-{published_at}",
            source_id=f"source-{source_location}-{evidence_location}-{published_at}",
            job_family_ids=["finance_legal"],
            job_category_ids=["accounting_audit"],
            location_ids=[evidence_location],
            period="2026-Q2",
            direction="increase",
            exact_claim="A reviewed claim.",
            metric_value=18,
            metric_unit="percent_qoq",
            citation="Page 12",
            confidence="medium",
        ),
    )
