from __future__ import annotations

from datetime import date

from backend.market_scout.pipelines.trend_tracker.ingest_external_outlook_sources_pipeline import (
    ExternalOutlookSourceConfig,
)
from backend.market_scout.schemas.trend_tracker.trend_external_evidence import TrendEvidence, TrendSource
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery, TrendQueryIntent
from backend.market_scout.services.trend_tracker.allowlisted_web_search_service import AllowlistedWebSearchResult
from backend.market_scout.services.trend_tracker.external_outlook_live_search_service import (
    ExternalOutlookLiveSearchService,
)


def test_live_search_extracts_and_returns_matching_evidence() -> None:
    searcher = FakeSearcher(
        [
            AllowlistedWebSearchResult(
                title="Vietnam IT outlook",
                url="https://topdev.vn/vietnam-tech-talents-report-topdev-2024",
                snippet="AI and software roles remain important.",
                raw_content=None,
                score=0.92,
                source_id="topdev",
                source_name="TopDev report",
                publisher="TopDev",
            )
        ]
    )
    extractor = FakeExtractor(
        [
            TrendEvidence(
                evidence_id="claim-1",
                source_id="live-source",
                job_family_ids=["digital_telecom"],
                job_category_ids=["software_it"],
                location_ids=["vietnam"],
                period="2026",
                direction="increase",
                exact_claim="AI and software hiring remains relevant.",
                metric_value=None,
                metric_unit=None,
                citation="Search result snippet",
                confidence="medium",
            )
        ]
    )

    matches = ExternalOutlookLiveSearchService(
        search_service=searcher,
        evidence_extractor=extractor,
        source_configs=[_source_config("topdev", "https://topdev.vn/vietnam-tech-talents-report-topdev-2024")],
    ).search("AI Vietnam 2026 outlook", _query("digital_telecom"))

    assert len(matches) == 1
    assert matches[0].source.url == "https://topdev.vn/vietnam-tech-talents-report-topdev-2024"
    assert matches[0].source.source_id.startswith("topdev__live__")
    assert matches[0].evidence.exact_claim == "AI and software hiring remains relevant."
    assert searcher.calls[0]["query"] == "AI Vietnam 2026 outlook"
    assert extractor.calls[0]["scopes"] == ("it",)
    assert "AI and software roles remain important." in extractor.calls[0]["content_text"]


def test_live_search_filters_claims_outside_query_scope() -> None:
    extractor = FakeExtractor(
        [
            TrendEvidence(
                evidence_id="wrong-family",
                source_id="live-source",
                job_family_ids=["commercial"],
                job_category_ids=["sales_business"],
                location_ids=["vietnam"],
                period="2026",
                direction="increase",
                exact_claim="Commercial claim.",
                metric_value=None,
                metric_unit=None,
                citation="Snippet",
                confidence="medium",
            ),
            TrendEvidence(
                evidence_id="right-family",
                source_id="live-source",
                job_family_ids=["digital_telecom"],
                job_category_ids=["software_it"],
                location_ids=["vietnam"],
                period="2026",
                direction="increase",
                exact_claim="IT claim.",
                metric_value=None,
                metric_unit=None,
                citation="Snippet",
                confidence="medium",
            ),
        ]
    )

    matches = ExternalOutlookLiveSearchService(
        search_service=FakeSearcher([_search_result()]),
        evidence_extractor=extractor,
        source_configs=[_source_config("topdev", "https://topdev.vn/vietnam-tech-talents-report-topdev-2024")],
    ).search("IT outlook", _query("digital_telecom"))

    assert [match.evidence.evidence_id for match in matches] == ["right-family"]


def test_live_search_uses_commercial_extraction_scope() -> None:
    extractor = FakeExtractor([])

    ExternalOutlookLiveSearchService(
        search_service=FakeSearcher([_search_result(source_id="robert-walters")]),
        evidence_extractor=extractor,
        source_configs=[
            _source_config("robert-walters", "https://www.robertwalters.com.vn/insights/hiring-advice")
        ],
    ).search("Sales marketing outlook", _query("commercial"))

    assert extractor.calls[0]["scopes"] == ("commercial",)


class FakeSearcher:
    def __init__(self, results: list[AllowlistedWebSearchResult]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        search_depth: str = "basic",
        include_raw_content: bool = False,
    ) -> list[AllowlistedWebSearchResult]:
        self.calls.append(
            {
                "query": query,
                "limit": limit,
                "search_depth": search_depth,
                "include_raw_content": include_raw_content,
            }
        )
        return self.results


class FakeExtractor:
    def __init__(self, evidence: list[TrendEvidence]) -> None:
        self.evidence = evidence
        self.calls: list[dict[str, object]] = []

    def extract(
        self,
        *,
        source: TrendSource,
        content_text: str,
        scopes: tuple[str, ...],
    ) -> list[TrendEvidence]:
        self.calls.append({"source": source, "content_text": content_text, "scopes": scopes})
        return self.evidence


def _query(job_family_id: str) -> TrendQuery:
    return TrendQuery(
        intent=TrendQueryIntent.EXTERNAL_OUTLOOK,
        job_family_id=job_family_id,
        location_id="vietnam",
    )


def _search_result(source_id: str = "topdev") -> AllowlistedWebSearchResult:
    return AllowlistedWebSearchResult(
        title="Outlook",
        url="https://topdev.vn/vietnam-tech-talents-report-topdev-2024",
        snippet="Market outlook.",
        raw_content=None,
        score=0.8,
        source_id=source_id,
        source_name="Source",
        publisher="Publisher",
    )


def _source_config(source_id: str, url: str) -> ExternalOutlookSourceConfig:
    return ExternalOutlookSourceConfig(
        source_id=source_id,
        source_name=f"{source_id} source",
        publisher=f"{source_id} publisher",
        source_type="labor_market_report",
        published_at=date(2026, 1, 1),
        scope_location_ids=["vietnam"],
        scope_period="2026",
        url=url,
        allowed_domain=url.split("/")[2],
        reliability_score=0.8,
        topics=["external_outlook"],
    )
