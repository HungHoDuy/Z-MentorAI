from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CurrentDemandSignal:
    signal: str
    demand_level: str
    active_job_count: int
    distinct_company_count: int
    period: str
    confidence: str
    limitations: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "signal": self.signal,
            "demand_level": self.demand_level,
            "active_job_count": self.active_job_count,
            "distinct_company_count": self.distinct_company_count,
            "period": self.period,
            "confidence": self.confidence,
            "limitations": list(self.limitations),
        }
