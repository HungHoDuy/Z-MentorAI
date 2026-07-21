from __future__ import annotations

from collections.abc import Sequence

from backend.market_scout.schemas.trend_tracker.current_demand import CurrentDemandSignal
from backend.market_scout.schemas.trend_tracker.job_family_trend_snapshot import JobFamilyTrendSnapshot
from backend.market_scout.schemas.trend_tracker.role_fact_match import RoleFactMatch


DEFAULT_MIN_ACTIVE_JOB_COUNT = 10
DEFAULT_MIN_DISTINCT_COMPANY_COUNT = 3
DEFAULT_HIGH_ACTIVE_JOB_COUNT = 25
DEFAULT_HIGH_DISTINCT_COMPANY_COUNT = 10
DEFAULT_ROLE_MIN_ACTIVE_JOB_COUNT = 3
DEFAULT_ROLE_MIN_DISTINCT_COMPANY_COUNT = 2
DEFAULT_ROLE_MODERATE_ACTIVE_JOB_COUNT = 10
DEFAULT_ROLE_HIGH_ACTIVE_JOB_COUNT = 25
DEFAULT_ROLE_HIGH_DISTINCT_COMPANY_COUNT = 5
DEFAULT_ROLE_SOURCE_LIMIT = 5


class CurrentDemandService:
    """Classify current demand from one snapshot without making a trend claim."""

    def __init__(
        self,
        *,
        min_active_job_count: int = DEFAULT_MIN_ACTIVE_JOB_COUNT,
        min_distinct_company_count: int = DEFAULT_MIN_DISTINCT_COMPANY_COUNT,
        high_active_job_count: int = DEFAULT_HIGH_ACTIVE_JOB_COUNT,
        high_distinct_company_count: int = DEFAULT_HIGH_DISTINCT_COMPANY_COUNT,
        role_min_active_job_count: int = DEFAULT_ROLE_MIN_ACTIVE_JOB_COUNT,
        role_min_distinct_company_count: int = DEFAULT_ROLE_MIN_DISTINCT_COMPANY_COUNT,
        role_moderate_active_job_count: int = DEFAULT_ROLE_MODERATE_ACTIVE_JOB_COUNT,
        role_high_active_job_count: int = DEFAULT_ROLE_HIGH_ACTIVE_JOB_COUNT,
        role_high_distinct_company_count: int = DEFAULT_ROLE_HIGH_DISTINCT_COMPANY_COUNT,
        role_source_limit: int = DEFAULT_ROLE_SOURCE_LIMIT,
    ) -> None:
        if min_active_job_count <= 0 or min_distinct_company_count <= 0:
            raise ValueError("Minimum sample thresholds must be positive.")
        if high_active_job_count < min_active_job_count:
            raise ValueError("high_active_job_count cannot be lower than the minimum threshold.")
        if high_distinct_company_count < min_distinct_company_count:
            raise ValueError("high_distinct_company_count cannot be lower than the minimum threshold.")
        for name, value in {
            "role_min_active_job_count": role_min_active_job_count,
            "role_min_distinct_company_count": role_min_distinct_company_count,
            "role_moderate_active_job_count": role_moderate_active_job_count,
            "role_high_active_job_count": role_high_active_job_count,
            "role_high_distinct_company_count": role_high_distinct_company_count,
            "role_source_limit": role_source_limit,
        }.items():
            if value <= 0:
                raise ValueError(f"{name} must be positive.")
        if role_moderate_active_job_count < role_min_active_job_count:
            raise ValueError("role_moderate_active_job_count cannot be lower than the role minimum threshold.")
        if role_high_active_job_count < role_moderate_active_job_count:
            raise ValueError("role_high_active_job_count cannot be lower than the role moderate threshold.")
        if role_high_distinct_company_count < role_min_distinct_company_count:
            raise ValueError("role_high_distinct_company_count cannot be lower than the role company minimum.")

        self.min_active_job_count = min_active_job_count
        self.min_distinct_company_count = min_distinct_company_count
        self.high_active_job_count = high_active_job_count
        self.high_distinct_company_count = high_distinct_company_count
        self.role_min_active_job_count = role_min_active_job_count
        self.role_min_distinct_company_count = role_min_distinct_company_count
        self.role_moderate_active_job_count = role_moderate_active_job_count
        self.role_high_active_job_count = role_high_active_job_count
        self.role_high_distinct_company_count = role_high_distinct_company_count
        self.role_source_limit = role_source_limit

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

    def evaluate_role_demand(
        self,
        matches: Sequence[RoleFactMatch],
        *,
        role_mention: str | None = None,
        location_id: str | None = None,
        period: str | None = None,
    ) -> CurrentDemandSignal:
        unique_matches = _dedupe_matches(matches)
        active_matches = [match for match in unique_matches if _is_active_match(match)]
        company_keys = {_company_key(match.company) for match in active_matches if _company_key(match.company)}
        active_job_count = len(active_matches)
        distinct_company_count = len(company_keys)

        if (
            active_job_count < self.role_min_active_job_count
            or distinct_company_count < self.role_min_distinct_company_count
        ):
            return CurrentDemandSignal(
                signal="insufficient_evidence",
                demand_level="limited",
                active_job_count=active_job_count,
                distinct_company_count=distinct_company_count,
                period=period,
                confidence="low",
                limitations=[
                    "The matched active-job sample is below the minimum role-level demand threshold.",
                    "This is current role demand from matched job postings, not a directional market trend.",
                ],
                role_mention=role_mention,
                location_id=location_id,
                matched_job_count=len(unique_matches),
                source_jobs=_source_jobs(unique_matches, limit=self.role_source_limit),
            )

        demand_level = self._role_demand_level(
            active_job_count=active_job_count,
            distinct_company_count=distinct_company_count,
        )
        confidence = "medium" if demand_level in {"moderate", "high"} else "low"
        return CurrentDemandSignal(
            signal=f"current_role_demand_{demand_level}",
            demand_level=demand_level,
            active_job_count=active_job_count,
            distinct_company_count=distinct_company_count,
            period=period,
            confidence=confidence,
            limitations=[
                "Demand level is based on active matched job postings and distinct company count for this role query.",
                "This is current role demand, not a conclusion that the market is increasing or decreasing.",
            ],
            role_mention=role_mention,
            location_id=location_id,
            matched_job_count=len(unique_matches),
            source_jobs=_source_jobs(unique_matches, limit=self.role_source_limit),
        )

    def _role_demand_level(self, *, active_job_count: int, distinct_company_count: int) -> str:
        if (
            active_job_count >= self.role_high_active_job_count
            and distinct_company_count >= self.role_high_distinct_company_count
        ):
            return "high"
        if active_job_count >= self.role_moderate_active_job_count:
            return "moderate"
        return "limited"

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


def _dedupe_matches(matches: Sequence[RoleFactMatch]) -> list[RoleFactMatch]:
    matches_by_key: dict[str, RoleFactMatch] = {}
    for match in matches:
        current = matches_by_key.get(match.job_key)
        if current is None or match.score > current.score:
            matches_by_key[match.job_key] = match
    return sorted(matches_by_key.values(), key=lambda item: (-item.score, item.job_title, item.job_key))


def _is_active_match(match: RoleFactMatch) -> bool:
    return match.is_active is not False


def _company_key(company: str | None) -> str | None:
    if not company:
        return None
    text = " ".join(str(company).casefold().split())
    return text or None


def _source_jobs(matches: Sequence[RoleFactMatch], *, limit: int) -> list[dict[str, object]]:
    return [
        {
            "job_key": match.job_key,
            "job_title": match.job_title,
            "company": match.company,
            "job_url": match.job_url,
            "score": round(match.score, 4),
            "match_method": match.match_method,
            "is_active": match.is_active,
        }
        for match in matches[:limit]
    ]
