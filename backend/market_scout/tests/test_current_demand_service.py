from datetime import date

from backend.market_scout.schemas.job_family_trend_snapshot import JobFamilyTrendSnapshot
from backend.market_scout.services.current_demand_service import CurrentDemandService


def test_returns_high_current_demand_for_large_broad_snapshot() -> None:
    signal = CurrentDemandService().evaluate(make_snapshot(active_jobs=28, companies=19))

    assert signal.signal == "current_demand_high"
    assert signal.demand_level == "high"
    assert signal.active_job_count == 28
    assert signal.distinct_company_count == 19
    assert signal.period == "2026-W25"
    assert signal.confidence == "low"


def test_returns_moderate_current_demand_when_minimum_sample_is_met() -> None:
    signal = CurrentDemandService().evaluate(make_snapshot(active_jobs=12, companies=4))

    assert signal.signal == "current_demand_moderate"
    assert signal.demand_level == "moderate"


def test_returns_insufficient_evidence_below_minimum_sample() -> None:
    signal = CurrentDemandService().evaluate(make_snapshot(active_jobs=3, companies=3))

    assert signal.signal == "insufficient_evidence"
    assert signal.demand_level == "limited"
    assert "not a directional trend" in signal.limitations[1]


def make_snapshot(*, active_jobs: int, companies: int) -> JobFamilyTrendSnapshot:
    return JobFamilyTrendSnapshot(
        period="2026-W25",
        period_start=date(2026, 6, 15),
        period_end=date(2026, 6, 21),
        job_family_id="commercial",
        location_id="hai-duong",
        observed_job_count=active_jobs + 5,
        active_job_count=active_jobs,
        unknown_active_job_count=0,
        updated_job_count=0,
        distinct_company_count=companies,
        source_job_counts={"careerviet": active_jobs + 5},
        taxonomy_version="job-category-taxonomy-v1",
    )
