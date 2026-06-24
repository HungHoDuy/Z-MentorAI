from dataclasses import asdict, dataclass, field
from typing import Any

from .entities import SalaryRange
from .enums import ConfidenceLevel, MarketScoutIntent
from .source import Source


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


@dataclass
class SalaryBenchmarkData:
    job_title: str
    location: str | None = None
    experience_years: int | None = None
    seniority: str | None = None
    salary_range: SalaryRange | None = None
    factors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.salary_range:
            data["salary_range"] = self.salary_range.to_dict()
        return data


@dataclass
class TrendInsight:
    name: str
    summary: str
    impact: str | None = None
    time_horizon: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM

    def __post_init__(self) -> None:
        if isinstance(self.confidence, str):
            self.confidence = ConfidenceLevel(self.confidence)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["confidence"] = _enum_value(self.confidence)
        return data


@dataclass
class TrendTrackerData:
    industry: str | None = None
    job_title: str | None = None
    location: str | None = None
    time_horizon: str | None = None
    growth_roles: list[TrendInsight] = field(default_factory=list)
    declining_roles: list[TrendInsight] = field(default_factory=list)
    market_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "industry": self.industry,
            "job_title": self.job_title,
            "location": self.location,
            "time_horizon": self.time_horizon,
            "growth_roles": [role.to_dict() for role in self.growth_roles],
            "declining_roles": [role.to_dict() for role in self.declining_roles],
            "market_signals": self.market_signals,
        }


@dataclass
class MarketScoutResponse:
    intent: MarketScoutIntent
    answer: str
    agent: str = "market_scout"
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    data: dict[str, Any] = field(default_factory=dict)
    sources: list[Source] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.answer = self.answer.strip()

        if not self.answer:
            raise ValueError("Answer must not be empty.")

        if isinstance(self.intent, str):
            self.intent = MarketScoutIntent(self.intent)

        if isinstance(self.confidence, str):
            self.confidence = ConfidenceLevel(self.confidence)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["intent"] = _enum_value(self.intent)
        data["confidence"] = _enum_value(self.confidence)
        data["sources"] = [source.to_dict() for source in self.sources]
        return data