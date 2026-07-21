from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class CurrentDemandSignal:
    signal: str
    demand_level: str
    active_job_count: int
    distinct_company_count: int
    period: str | None
    confidence: str
    limitations: list[str]
    role_mention: str | None = None
    location_id: str | None = None
    matched_job_count: int | None = None
    source_jobs: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "signal": self.signal,
            "demand_level": self.demand_level,
            "active_job_count": self.active_job_count,
            "distinct_company_count": self.distinct_company_count,
            "period": self.period,
            "confidence": self.confidence,
            "limitations": list(self.limitations),
            "role_mention": self.role_mention,
            "location_id": self.location_id,
            "matched_job_count": self.matched_job_count,
            "source_jobs": list(self.source_jobs),
        }
