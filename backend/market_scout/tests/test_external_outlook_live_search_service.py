from __future__ import annotations

from datetime import date

from backend.market_scout.pipelines.trend_tracker.ingest_external_outlook_sources_pipeline import ExternalOutlookSourceConfig
from backend.market_scout.services.trend_tracker.allowlisted_web_search_service import AllowlistedWebSearchResult
from backend.market_scout.services.trend_tracker.external_outlook_live_search_service import ExternalOutlookLiveSearchService


def test_live_search_returns_allowlisted_content_without_job_family() -> None:
    searcher = FakeSearcher([_search_result(raw_content="AI and software roles remain important.")])
    results = ExternalOutlookLiveSearchService(
        search_service=searcher,
        source_configs=[_source_config()],
    ).search("Nhung cong viec nao co nguy co bi AI thay the?")

    assert len(results) == 1
    assert results[0].source.url == "https://topdev.vn/report"
    assert results[0].source.source_id.startswith("topdev__live__")
    assert "AI and software roles remain important." in results[0].content
    assert searcher.calls[0]["query"] == "Nhung cong viec nao co nguy co bi AI thay the?"
    assert searcher.calls[0]["limit"] == 5
    assert searcher.calls[0]["include_raw_content"] is True


def test_live_search_limits_results_to_five() -> None:
    searcher = FakeSearcher([_search_result(url=f"https://topdev.vn/report-{index}") for index in range(7)])
    results = ExternalOutlookLiveSearchService(
        search_service=searcher,
        source_configs=[_source_config(url="https://topdev.vn")],
    ).search("market outlook")
    assert len(results) == 5


def test_live_search_truncates_each_source_to_configured_character_limit() -> None:
    results = ExternalOutlookLiveSearchService(
        search_service=FakeSearcher([_search_result(raw_content="x" * 10_000)]),
        source_configs=[_source_config()],
        max_content_characters_per_source=5_000,
    ).search("market outlook")
    assert len(results[0].content) == 5_000


def test_live_search_filters_low_reliability_sources() -> None:
    results = ExternalOutlookLiveSearchService(
        search_service=FakeSearcher([_search_result()]),
        source_configs=[_source_config(reliability_score=0.6)],
    ).search("market outlook")
    assert results == []


class FakeSearcher:
    def __init__(self, results: list[AllowlistedWebSearchResult]) -> None:
        self.results = results
        self.calls: list[dict[str, object]] = []

    def search(self, query: str, *, limit: int = 5, search_depth: str = "basic", include_raw_content: bool = False) -> list[AllowlistedWebSearchResult]:
        self.calls.append({"query": query, "limit": limit, "search_depth": search_depth, "include_raw_content": include_raw_content})
        return self.results


def _search_result(*, url: str = "https://topdev.vn/report", raw_content: str | None = None) -> AllowlistedWebSearchResult:
    return AllowlistedWebSearchResult(
        title="Vietnam outlook",
        url=url,
        snippet="Market outlook.",
        raw_content=raw_content,
        score=0.8,
        source_id="topdev",
        source_name="TopDev report",
        publisher="TopDev",
    )


def _source_config(*, url: str = "https://topdev.vn/report", reliability_score: float = 0.8) -> ExternalOutlookSourceConfig:
    return ExternalOutlookSourceConfig(
        source_id="topdev",
        source_name="TopDev source",
        publisher="TopDev",
        source_type="labor_market_report",
        published_at=date(2026, 1, 1),
        scope_location_ids=["vietnam"],
        scope_period="2026",
        url=url,
        allowed_domain="topdev.vn",
        reliability_score=reliability_score,
        topics=["external_outlook"],
    )
