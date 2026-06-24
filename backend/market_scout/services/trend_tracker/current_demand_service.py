from __future__ import annotations

from backend.market_scout.schemas.trend_tracker.current_demand import CurrentDemandSignal
from backend.market_scout.schemas.trend_tracker.job_family_trend_snapshot import JobFamilyTrendSnapshot


DEFAULT_MIN_ACTIVE_JOB_COUNT = 10
DEFAULT_MIN_DISTINCT_COMPANY_COUNT = 3
DEFAULT_HIGH_ACTIVE_JOB_COUNT = 25
DEFAULT_HIGH_DISTINCT_COMPANY_COUNT = 10


class CurrentDemandService:
    """Classify current demand from one snapshot without making a trend claim."""

    def __init__(
        self,
        *,
        min_active_job_count: int = DEFAULT_MIN_ACTIVE_JOB_COUNT,
        min_distinct_company_count: int = DEFAULT_MIN_DISTINCT_COMPANY_COUNT,
        high_active_job_count: int = DEFAULT_HIGH_ACTIVE_JOB_COUNT,
        high_distinct_company_count: int = DEFAULT_HIGH_DISTINCT_COMPANY_COUNT,
    ) -> None:
        if min_active_job_count <= 0 or min_distinct_company_count <= 0:
            raise ValueError("Minimum sample thresholds must be positive.")
        if high_active_job_count < min_active_job_count:
            raise ValueError("high_active_job_count cannot be lower than the minimum threshold.")
        if high_distinct_company_count < min_distinct_company_count:
            raise ValueError("high_distinct_company_count cannot be lower than the minimum threshold.")

        self.min_active_job_count = min_active_job_count
        self.min_distinct_company_count = min_distinct_company_count
        self.high_active_job_count = high_active_job_count
        self.high_distinct_company_count = high_distinct_company_count

    def evaluate(self, snapshot: JobFamilyTrendSnapshot) -> CurrentDemandSignal:
        if not self._has_minimum_sample(snapshot):
            return CurrentDemandSignal(
                signal="insufficient_evidence",
                demand_level="limited",
                active_job_count=snapshot.active_job_count,
                distinct_company_count=snapshot.distinct_company_count,
                period=snapshot.period,
                confidence="low",
                limitations=[
                    "The snapshot does not meet the minimum active-job and company sample thresholds.",
                    "This is a current-demand baseline, not a directional trend.",
                ],
            )

        demand_level = "high" if self._has_high_demand(snapshot) else "moderate"
        return CurrentDemandSignal(
            signal=f"current_demand_{demand_level}",
            demand_level=demand_level,
            active_job_count=snapshot.active_job_count,
            distinct_company_count=snapshot.distinct_company_count,
            period=snapshot.period,
            confidence="low",
            limitations=[
                "Only one internal snapshot is available; no growth or decline is inferred.",
                "Demand level is based on active job and distinct company counts for this family-location snapshot.",
            ],
        )

    def _has_minimum_sample(self, snapshot: JobFamilyTrendSnapshot) -> bool:
        return (
            snapshot.active_job_count >= self.min_active_job_count
            and snapshot.distinct_company_count >= self.min_distinct_company_count
        )

    def _has_high_demand(self, snapshot: JobFamilyTrendSnapshot) -> bool:
        return (
            snapshot.active_job_count >= self.high_active_job_count
            and snapshot.distinct_company_count >= self.high_distinct_company_count
        )
