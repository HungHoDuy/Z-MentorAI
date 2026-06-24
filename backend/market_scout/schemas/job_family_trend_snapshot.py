from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class JobFamilyTrendSnapshot:
    """Weekly demand aggregate for a taxonomy job family in one location."""

    period: str
    period_start: date
    period_end: date
    job_family_id: str
    location_id: str
    observed_job_count: int
    active_job_count: int
    unknown_active_job_count: int
    updated_job_count: int
    distinct_company_count: int
    source_job_counts: dict[str, int]
    taxonomy_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "job_family_id": self.job_family_id,
            "location_id": self.location_id,
            "observed_job_count": self.observed_job_count,
            "active_job_count": self.active_job_count,
            "unknown_active_job_count": self.unknown_active_job_count,
            "updated_job_count": self.updated_job_count,
            "distinct_company_count": self.distinct_company_count,
            "source_job_counts": dict(sorted(self.source_job_counts.items())),
            "taxonomy_version": self.taxonomy_version,
        }
