from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from backend.market_scout.pipelines.trend_tracker.ingest_external_outlook_sources_pipeline import (
    ExternalOutlookSourceConfig,
    load_external_outlook_source_configs,
)
from backend.market_scout.repositories.salary_benchmark.salary_repository import load_env_file


DEFAULT_TAVILY_SEARCH_ENDPOINT = "https://api.tavily.com/search"
DEFAULT_TAVILY_SEARCH_DEPTH = "basic"
DEFAULT_TAVILY_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class AllowlistedWebSearchResult:
    title: str
    url: str
    snippet: str | None
    raw_content: str | None
    score: float | None
    source_id: str
    source_name: str
    publisher: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "raw_content": self.raw_content,
            "score": self.score,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "publisher": self.publisher,
        }


TavilyHttpPost = Callable[[str, Mapping[str, str], Mapping[str, Any], int], Mapping[str, Any]]


class AllowlistedWebSearchService:
    """Search only configured external-outlook domains through Tavily."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        source_configs: list[ExternalOutlookSourceConfig] | None = None,
        source_config_path: Path | None = None,
        http_post: TavilyHttpPost | None = None,
        endpoint: str = DEFAULT_TAVILY_SEARCH_ENDPOINT,
        timeout_seconds: int = DEFAULT_TAVILY_TIMEOUT_SECONDS,
    ) -> None:
        load_env_file()
        self.api_key = api_key if api_key is not None else os.getenv("TAVILY_API_KEY")
        self.source_configs = source_configs or load_external_outlook_source_configs(source_config_path)
        self.http_post = http_post or tavily_http_post
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        search_depth: str = DEFAULT_TAVILY_SEARCH_DEPTH,
        include_raw_content: bool = False,
    ) -> list[AllowlistedWebSearchResult]:
        query_text = " ".join(str(query or "").split())
        if not query_text:
            raise ValueError("query must not be empty.")
        if limit <= 0:
            raise ValueError("limit must be positive.")
        if not self.api_key:
            raise RuntimeError("TAVILY_API_KEY is required for live external outlook search.")

        payload = {
            "query": query_text,
            "include_domains": self._allowed_domains(),
            "max_results": limit,
            "search_depth": search_depth,
            "include_raw_content": include_raw_content,
        }
        response = self.http_post(
            self.endpoint,
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            payload,
            self.timeout_seconds,
        )
        return self._results_from_response(response, limit=limit)

    def _allowed_domains(self) -> list[str]:
        domains = {_normalize_domain(config.allowed_domain) for config in self.source_configs}
        return sorted(domain for domain in domains if domain)

    def _results_from_response(
        self,
        response: Mapping[str, Any],
        *,
        limit: int,
    ) -> list[AllowlistedWebSearchResult]:
        items = response.get("results")
        if not isinstance(items, list):
            return []

        seen_urls: set[str] = set()
        results: list[AllowlistedWebSearchResult] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            url = _optional_text(item.get("url"))
            if not url:
                continue
            canonical_url = _canonical_url(url)
            if canonical_url in seen_urls:
                continue
            source = _source_for_url(url, self.source_configs)
            if source is None:
                continue

            seen_urls.add(canonical_url)
            results.append(
                AllowlistedWebSearchResult(
                    title=_optional_text(item.get("title")) or source.source_name,
                    url=url,
                    snippet=_optional_text(item.get("content")) or _optional_text(item.get("snippet")),
                    raw_content=_optional_text(item.get("raw_content")),
                    score=_optional_score(item.get("score")),
                    source_id=source.source_id,
                    source_name=source.source_name,
                    publisher=source.publisher,
                )
            )
            if len(results) >= limit:
                break
        return results


def tavily_http_post(
    endpoint: str,
    headers: Mapping[str, str],
    payload: Mapping[str, Any],
    timeout_seconds: int,
) -> Mapping[str, Any]:
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=dict(headers),
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _source_for_url(
    url: str,
    source_configs: list[ExternalOutlookSourceConfig],
) -> ExternalOutlookSourceConfig | None:
    canonical_url = _canonical_url(url)
    for config in source_configs:
        if canonical_url.startswith(_canonical_url(config.url)):
            return config

    host = _normalize_domain(urlparse(url).hostname)
    for config in source_configs:
        allowed_domain = _normalize_domain(config.allowed_domain)
        if host == allowed_domain or host.endswith(f".{allowed_domain}"):
            return config
    return None


def _canonical_url(url: str) -> str:
    return str(url).strip().rstrip("/")


def _normalize_domain(value: str | None) -> str:
    domain = str(value or "").strip().casefold()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _optional_score(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


