from __future__ import annotations

from dataclasses import dataclass

from backend.market_scout.schemas.trend_tracker.trend_external_evidence import TrendSource


@dataclass(frozen=True)
class ExternalOutlookWebResult:
    """Allowlisted web content prepared for external-outlook summarization."""

    source: TrendSource
    content: str
    snippet: str | None
    search_score: float | None
