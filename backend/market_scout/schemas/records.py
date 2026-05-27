from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .enums import ConfidenceLevel, SalaryPeriod
from .source import Source


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


@dataclass
class ExtractedTrendRecord:
    source: Source
    market_signal: str
    trend_type: str = "growth"
    industry: str | None = None
    job_title: str | None = None
    location: str | None = None
    time_horizon: str | None = None
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    evidence_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.market_signal = self.market_signal.strip()
        self.trend_type = self.trend_type.strip().lower()

        if not self.market_signal:
            raise ValueError("Trend record market_signal must not be empty.")

        if isinstance(self.confidence, str):
            self.confidence = ConfidenceLevel(self.confidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "market_signal": self.market_signal,
            "trend_type": self.trend_type,
            "industry": self.industry,
            "job_title": self.job_title,
            "location": self.location,
            "time_horizon": self.time_horizon,
            "confidence": _enum_value(self.confidence),
            "evidence_text": self.evidence_text,
            "metadata": self.metadata,
        }


@dataclass
class ExtractedSalaryRecord:
    source: Source
    job_title: str
    salary_min: float
    salary_max: float
    currency: str
    location: str | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    salary_median: float | None = None
    period: SalaryPeriod = SalaryPeriod.MONTHLY
    evidence_text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.job_title = self.job_title.strip()
        self.currency = self.currency.strip().upper()

        if not self.job_title:
            raise ValueError("Salary record job_title must not be empty.")

        if self.salary_min > self.salary_max:
            raise ValueError("Salary record salary_min must be less than or equal to salary_max.")

        if isinstance(self.period, str):
            self.period = SalaryPeriod(self.period)

        if self.salary_median is None:
            self.salary_median = (self.salary_min + self.salary_max) / 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "job_title": self.job_title,
            "location": self.location,
            "experience_min": self.experience_min,
            "experience_max": self.experience_max,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_median": self.salary_median,
            "currency": self.currency,
            "period": _enum_value(self.period),
            "evidence_text": self.evidence_text,
            "metadata": self.metadata,
        }
