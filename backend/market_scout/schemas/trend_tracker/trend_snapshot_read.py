from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from backend.market_scout.schemas.trend_tracker.job_family_trend_snapshot import JobFamilyTrendSnapshot


@dataclass(frozen=True)
class TrendSnapshotReadResult:
    snapshot_id: str
    snapshot: JobFamilyTrendSnapshot
    freshness_days: int
    freshness_status: str
    sample_status: str

    @property
    def period(self) -> str:
        return self.snapshot.period
