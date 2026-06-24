from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MarketScoutIntent(str, Enum):
    SALARY_BENCHMARK = "salary_benchmark"
    TREND_TRACKER = "trend_tracker"
    JOB_DEMAND_FORECAST = "job_demand_forecast"
    INDUSTRY_DECLINE_RISK = "industry_decline_risk"
    MIXED = "mixed"
    UNCLEAR = "unclear"

    @classmethod
    def from_value(cls, value: Any) -> "MarketScoutIntent":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value))
        except ValueError:
            return cls.UNCLEAR


@dataclass(frozen=True)
class MarketScoutRequest:
    user_query: str
    user_context: dict[str, Any] = field(default_factory=dict)
    entities_hint: dict[str, Any] | None = None
    intent_hint: MarketScoutIntent | str | None = None


@dataclass(frozen=True)
class MarketScoutResponse:
    agent: str
    intent: MarketScoutIntent
    answer: str
    confidence: str
    data: dict[str, Any] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "intent": self.intent.value,
            "answer": self.answer,
            "confidence": self.confidence,
            "data": self.data,
            "sources": self.sources,
            "limitations": self.limitations,
        }
