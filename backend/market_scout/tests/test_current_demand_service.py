from datetime import date

from backend.market_scout.schemas.trend_tracker.job_family_trend_snapshot import JobFamilyTrendSnapshot
from backend.market_scout.schemas.trend_tracker.role_fact_match import RoleFactMatch
from backend.market_scout.services.trend_tracker.current_demand_service import CurrentDemandService


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



def test_evaluate_role_demand_returns_high_for_many_active_jobs_and_companies() -> None:
    matches = [
        make_match(index=index, company=f"Company {index % 6}", is_active=True)
        for index in range(25)
    ]

    signal = CurrentDemandService().evaluate_role_demand(
        matches,
        role_mention="backend engineer",
        location_id="ha-noi",
        period="2026-W25",
    )

    assert signal.signal == "current_role_demand_high"
    assert signal.demand_level == "high"
    assert signal.active_job_count == 25
    assert signal.distinct_company_count == 6
    assert signal.confidence == "medium"
    assert signal.role_mention == "backend engineer"
    assert signal.location_id == "ha-noi"
    assert signal.matched_job_count == 25
    assert len(signal.source_jobs) == 5
    assert signal.to_dict()["source_jobs"][0]["job_url"] == "https://example.com/job-0"


def test_evaluate_role_demand_returns_limited_for_small_but_sufficient_role_sample() -> None:
    matches = [
        make_match(index=1, company="Company A", is_active=True),
        make_match(index=2, company="Company B", is_active=True),
        make_match(index=3, company="Company B", is_active=True),
    ]

    signal = CurrentDemandService().evaluate_role_demand(matches, role_mention="sales b2b")

    assert signal.signal == "current_role_demand_limited"
    assert signal.demand_level == "limited"
    assert signal.active_job_count == 3
    assert signal.distinct_company_count == 2
    assert signal.confidence == "low"


def test_evaluate_role_demand_returns_insufficient_when_active_sample_is_too_small() -> None:
    matches = [
        make_match(index=1, company="Company A", is_active=True),
        make_match(index=2, company="Company B", is_active=False),
        make_match(index=3, company="Company C", is_active=False),
    ]

    signal = CurrentDemandService().evaluate_role_demand(matches, role_mention="qa engineer")

    assert signal.signal == "insufficient_evidence"
    assert signal.active_job_count == 1
    assert signal.distinct_company_count == 1


def test_evaluate_role_demand_deduplicates_matches_by_job_key() -> None:
    matches = [
        make_match(index=1, job_key="same", company="Company A", score=0.7, is_active=True),
        make_match(index=2, job_key="same", company="Company A", score=0.9, is_active=True),
        make_match(index=3, company="Company B", is_active=True),
        make_match(index=4, company="Company C", is_active=True),
    ]

    signal = CurrentDemandService().evaluate_role_demand(matches, role_mention="business analyst")

    assert signal.matched_job_count == 3
    assert signal.active_job_count == 3
    same_source = next(source for source in signal.source_jobs if source["job_key"] == "same")
    assert same_source["score"] == 0.9


def make_match(
    *,
    index: int,
    company: str,
    job_key: str | None = None,
    score: float | None = None,
    is_active: bool | None = True,
) -> RoleFactMatch:
    return RoleFactMatch(
        job_key=job_key or f"job-{index}",
        job_title=f"Role {index}",
        company=company,
        job_url=f"https://example.com/job-{index}",
        job_category_ids=["software_it"],
        job_family_ids=["digital_telecom"],
        location_ids=["ha-noi"],
        is_active=is_active,
        score=score if score is not None else 1 - (index * 0.001),
        match_method="hybrid",
    )
