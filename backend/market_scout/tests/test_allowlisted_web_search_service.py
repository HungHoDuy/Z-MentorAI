from __future__ import annotations

from datetime import date
from typing import Any, Mapping

import pytest

from backend.market_scout.pipelines.trend_tracker.ingest_external_outlook_sources_pipeline import (
    ExternalOutlookSourceConfig,
)
from backend.market_scout.services.trend_tracker.allowlisted_web_search_service import (
    AllowlistedWebSearchService,
)


def test_search_uses_tavily_allowlist_and_filters_returned_domains() -> None:
    http_post = FakeTavilyPost(
        {
            "results": [
                {
                    "title": "Allowed trend result",
                    "url": "https://topdev.vn/vietnam-tech-talents-report-topdev-2024",
                    "content": "Vietnam IT hiring context.",
                    "score": 0.91,
                },
                {
                    "title": "Rejected result",
                    "url": "https://random.example.com/post",
                    "content": "This should not pass the allowlist.",
                    "score": 0.99,
                },
            ]
        }
    )
    service = AllowlistedWebSearchService(
        api_key="test-key",
        source_configs=[_source_config("topdev", "https://topdev.vn/vietnam-tech-talents-report-topdev-2024")],
        http_post=http_post,
    )

    results = service.search("IT Vietnam outlook", limit=5)

    assert [result.url for result in results] == [
        "https://topdev.vn/vietnam-tech-talents-report-topdev-2024"
    ]
    assert results[0].source_id == "topdev"
    assert http_post.calls[0]["payload"]["include_domains"] == ["topdev.vn"]
    assert http_post.calls[0]["headers"]["Authorization"] == "Bearer test-key"


def test_search_deduplicates_urls() -> None:
    source = _source_config("manpower", "https://www.manpower.com.vn/nb/insights/meos/2026")
    service = AllowlistedWebSearchService(
        api_key="test-key",
        source_configs=[source],
        http_post=FakeTavilyPost(
            {
                "results": [
                    {
                        "title": "First",
                        "url": "https://www.manpower.com.vn/nb/insights/meos/2026/",
                        "content": "First copy.",
                    },
                    {
                        "title": "Second",
                        "url": "https://www.manpower.com.vn/nb/insights/meos/2026",
                        "content": "Second copy.",
                    },
                ]
            }
        ),
    )

    results = service.search("sales hiring", limit=5)

    assert len(results) == 1
    assert results[0].title == "First"


def test_search_requires_api_key() -> None:
    service = AllowlistedWebSearchService(
        api_key="",
        source_configs=[_source_config("topdev", "https://topdev.vn/vietnam-tech-talents-report-topdev-2024")],
        http_post=FakeTavilyPost({"results": []}),
    )

    with pytest.raises(RuntimeError, match="TAVILY_API_KEY"):
        service.search("IT outlook")


class FakeTavilyPost:
    def __init__(self, response: Mapping[str, Any]) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        endpoint: str,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: int,
    ) -> Mapping[str, Any]:
        self.calls.append(
            {
                "endpoint": endpoint,
                "headers": dict(headers),
                "payload": dict(payload),
                "timeout_seconds": timeout_seconds,
            }
        )
        return self.response


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
