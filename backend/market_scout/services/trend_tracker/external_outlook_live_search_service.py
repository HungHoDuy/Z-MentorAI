from __future__ import annotations

import hashlib
from datetime import date
from typing import Protocol

from backend.market_scout.pipelines.trend_tracker.ingest_external_outlook_sources_pipeline import (
    ExternalOutlookSourceConfig,
    load_external_outlook_source_configs,
)
from backend.market_scout.repositories.trend_tracker.trend_evidence_repository import (
    select_external_outlook_evidence,
)
from backend.market_scout.schemas.trend_tracker.trend_external_evidence import (
    TrendEvidence,
    TrendEvidenceMatch,
    TrendSource,
)
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery
from backend.market_scout.services.trend_tracker.allowlisted_web_search_service import (
    AllowlistedWebSearchResult,
    AllowlistedWebSearchService,
)
from backend.market_scout.services.trend_tracker.external_outlook_evidence_extractor import (
    ExternalOutlookEvidenceExtractor,
)


DEFAULT_LIVE_SEARCH_RESULT_LIMIT = 5
DEFAULT_LIVE_EVIDENCE_LIMIT = 5
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


class ExternalOutlookExtractor(Protocol):
    def extract(
        self,
        *,
        source: TrendSource,
        content_text: str,
        scopes: tuple[str, ...],
    ) -> list[TrendEvidence]:
        ...


class ExternalOutlookLiveSearchService:
    """Build temporary cited external-outlook evidence from allowlisted live web search."""

    def __init__(
        self,
        *,
        search_service: ExternalOutlookSearcher | None = None,
        evidence_extractor: ExternalOutlookExtractor | None = None,
        source_configs: list[ExternalOutlookSourceConfig] | None = None,
        min_reliability_score: float = DEFAULT_MIN_LIVE_SOURCE_RELIABILITY_SCORE,
        search_result_limit: int = DEFAULT_LIVE_SEARCH_RESULT_LIMIT,
        evidence_limit: int = DEFAULT_LIVE_EVIDENCE_LIMIT,
        include_raw_content: bool = True,
    ) -> None:
        if not 0 <= min_reliability_score <= 1:
            raise ValueError("min_reliability_score must be between 0 and 1.")
        if search_result_limit <= 0:
            raise ValueError("search_result_limit must be positive.")
        if evidence_limit <= 0:
            raise ValueError("evidence_limit must be positive.")

        self.source_configs = source_configs or load_external_outlook_source_configs()
        self.search_service = search_service or AllowlistedWebSearchService(source_configs=self.source_configs)
        self.evidence_extractor = evidence_extractor or ExternalOutlookEvidenceExtractor()
        self.min_reliability_score = min_reliability_score
        self.search_result_limit = search_result_limit
        self.evidence_limit = evidence_limit
        self.include_raw_content = include_raw_content

    def search(self, user_query: str, query: TrendQuery) -> list[TrendEvidenceMatch]:
        search_results = self.search_service.search(
            user_query,
            limit=self.search_result_limit,
            include_raw_content=self.include_raw_content,
        )
        candidates: list[TrendEvidenceMatch] = []
        for result in search_results:
            source_config = self._source_config(result.source_id)
            if source_config is None:
                continue

            source = _trend_source_from_search_result(result, source_config)
            content_text = _content_text(result)
            if not content_text:
                continue

            for evidence in self.evidence_extractor.extract(
                source=source,
                content_text=content_text,
                scopes=_scopes_for_query(query),
            ):
                candidates.append(TrendEvidenceMatch(source=source, evidence=evidence))

        return select_external_outlook_evidence(
            candidates,
            job_family_id=query.job_family_id,
            location_ids=_external_location_scope(query.location_id),
            published_after=None,
            min_reliability_score=self.min_reliability_score,
            limit=self.evidence_limit,
        )

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


def _scopes_for_query(query: TrendQuery) -> tuple[str, ...]:
    if query.job_family_id == "digital_telecom":
        return ("it",)
    if query.job_family_id == "commercial":
        return ("commercial",)
    return ("it", "commercial")


def _external_location_scope(location_id: str | None) -> list[str]:
    if not location_id or location_id in {"vietnam", "all"}:
        return ["vietnam", "global"]
    return list(dict.fromkeys([location_id, "vietnam", "global"]))


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
