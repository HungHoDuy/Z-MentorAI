from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.market_scout.schemas import MarketScoutIntent
from backend.market_scout.schemas.salary_benchmark.salary import SalarySearchQuery
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQueryIntent


@dataclass(frozen=True)
class TrendQueryUnderstanding:
    """LLM-parsed Trend Tracker query intent and entity hints."""

    intent: TrendQueryIntent
    role_mention: str | None = None
    location_text: str | None = None
    job_category_hint: str | None = None
    job_family_hint: str | None = None
    requested_signal: str | None = None
    confidence: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "role_mention": self.role_mention,
            "location_text": self.location_text,
            "job_category_hint": self.job_category_hint,
            "job_family_hint": self.job_family_hint,
            "requested_signal": self.requested_signal,
            "confidence": self.confidence,
        }


@dataclass(frozen=True)
class MarketScoutQueryUnderstanding:
    """Top-level Market Scout query understanding result."""

    intent: MarketScoutIntent
    salary_query: SalarySearchQuery | None = None
    trend_query: TrendQueryUnderstanding | None = None
    confidence: str = "low"
    source: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent.value,
            "salary_query": _salary_query_to_dict(self.salary_query),
            "trend_query": self.trend_query.to_dict() if self.trend_query else None,
            "confidence": self.confidence,
            "source": self.source,
        }


def _salary_query_to_dict(query: SalarySearchQuery | None) -> dict[str, Any] | None:
    if query is None:
        return None
    return {
        "raw_query": query.raw_query,
        "job_title": query.job_title,
        "job_title_normalized": query.job_title_normalized,
        "location": query.location,
        "location_normalized": query.location_normalized,
        "experience_years": query.experience_years,
        "currency": query.currency,
    }
