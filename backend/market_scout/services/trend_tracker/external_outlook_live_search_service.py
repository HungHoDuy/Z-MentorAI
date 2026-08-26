from __future__ import annotations

import hashlib
from datetime import date
from typing import Protocol

from backend.market_scout.pipelines.trend_tracker.ingest_external_outlook_sources_pipeline import (
    ExternalOutlookSourceConfig,
    load_external_outlook_source_configs,
)
from backend.market_scout.schemas.trend_tracker.external_outlook_web_result import ExternalOutlookWebResult
from backend.market_scout.schemas.trend_tracker.trend_external_evidence import TrendSource
from backend.market_scout.services.trend_tracker.allowlisted_web_search_service import (
    AllowlistedWebSearchResult,
    AllowlistedWebSearchService,
)
DEFAULT_LIVE_SEARCH_RESULT_LIMIT = 5
DEFAULT_MAX_CONTENT_CHARACTERS_PER_SOURCE = 8_000
DEFAULT_MIN_LIVE_SOURCE_RELIABILITY_SCORE = 0.7


class ExternalOutlookSearcher(Protocol):
    def search(
        self,
        query: str,
        *,
        limit: int = DEFAULT_LIVE_SEARCH_RESULT_LIMIT,
        search_depth: str = "basic",
        include_raw_content: bool = False,
    ) -> list[AllowlistedWebSearchResult]:
        ...


class ExternalOutlookLiveSearchService:
    """Prepare allowlisted live web results for external-outlook summarization."""

    def __init__(
        self,
        *,
        search_service: ExternalOutlookSearcher | None = None,
        source_configs: list[ExternalOutlookSourceConfig] | None = None,
        min_reliability_score: float = DEFAULT_MIN_LIVE_SOURCE_RELIABILITY_SCORE,
        search_result_limit: int = DEFAULT_LIVE_SEARCH_RESULT_LIMIT,
        max_content_characters_per_source: int = DEFAULT_MAX_CONTENT_CHARACTERS_PER_SOURCE,
        include_raw_content: bool = True,
    ) -> None:
        if not 0 <= min_reliability_score <= 1:
            raise ValueError("min_reliability_score must be between 0 and 1.")
        if search_result_limit <= 0:
            raise ValueError("search_result_limit must be positive.")
        if max_content_characters_per_source <= 0:
            raise ValueError("max_content_characters_per_source must be positive.")

        self.source_configs = source_configs or load_external_outlook_source_configs()
        self.search_service = search_service or AllowlistedWebSearchService(source_configs=self.source_configs)
        self.min_reliability_score = min_reliability_score
        self.search_result_limit = search_result_limit
        self.max_content_characters_per_source = max_content_characters_per_source
        self.include_raw_content = include_raw_content

    def search(self, user_query: str) -> list[ExternalOutlookWebResult]:
        search_results = self.search_service.search(
            user_query,
            limit=self.search_result_limit,
            include_raw_content=self.include_raw_content,
        )
        candidates: list[ExternalOutlookWebResult] = []
        for result in search_results:
            source_config = self._source_config(result.source_id)
            if source_config is None or source_config.reliability_score < self.min_reliability_score:
                continue

            source = _trend_source_from_search_result(result, source_config)
            content_text = _content_text(result)[: self.max_content_characters_per_source]
            if not content_text:
                continue
            candidates.append(
                ExternalOutlookWebResult(
                    source=source,
                    content=content_text,
                    snippet=result.snippet,
                    search_score=result.score,
                )
            )

        return candidates[: self.search_result_limit]

    def _source_config(self, source_id: str) -> ExternalOutlookSourceConfig | None:
        for config in self.source_configs:
            if config.source_id == source_id:
                return config
        return None


def _trend_source_from_search_result(
    result: AllowlistedWebSearchResult,
    config: ExternalOutlookSourceConfig,
) -> TrendSource:
    return TrendSource(
        source_id=f"{config.source_id}__live__{_short_hash(result.url)}",
        source_name=result.title or config.source_name,
        publisher=config.publisher,
        source_type="allowlisted_web_result",
        published_at=config.published_at,
        fetched_at=date.today(),
        reliability_score=config.reliability_score,
        scope_location_ids=list(config.scope_location_ids),
        scope_period=config.scope_period,
        url=result.url,
        content_hash=f"sha256:{_short_hash(_content_text(result))}",
        notes="Allowlisted live web search result.",
    )


def _content_text(result: AllowlistedWebSearchResult) -> str:
    parts = [
        f"Title: {result.title}",
        f"URL: {result.url}",
        f"Snippet: {result.snippet or ''}",
        f"Content: {result.raw_content or ''}",
    ]
    return "\n".join(part for part in parts if part.strip())


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
