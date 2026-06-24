from datetime import date

from backend.market_scout.schemas.trend_tracker.job_category_trend import JobCategoryTrendJobFact
from backend.market_scout.services.trend_tracker.job_family_trend_snapshot_builder import (
    JobFamilyTrendSnapshotBuilder,
)


def test_builds_job_family_location_snapshots_and_excludes_non_trend_categories() -> None:
    snapshots = JobFamilyTrendSnapshotBuilder().build(
        [
            make_fact(
                "accounting-1",
                category_ids=["accounting_audit"],
                family_ids=["finance_legal"],
                company_key="company-a",
                source_updated_at=date(2026, 6, 17),
            ),
            make_fact(
                "banking-1",
                category_ids=["banking"],
                family_ids=["finance_legal"],
                company_key="company-b",
                source_updated_at=date(2026, 6, 10),
            ),
            make_fact(
                "graduate-1",
                category_ids=["graduate_internship"],
                family_ids=["career_stage"],
                company_key="company-c",
            ),
            make_fact(
                "future-1",
                category_ids=["banking"],
                family_ids=["finance_legal"],
                company_key="company-d",
                source_updated_at=date(2026, 6, 22),
            ),
        ],
        period_start=date(2026, 6, 15),
        period_end=date(2026, 6, 21),
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.period == "2026-W25"
    assert snapshot.job_family_id == "finance_legal"
    assert snapshot.location_id == "ho-chi-minh"
    assert snapshot.observed_job_count == 2
    assert snapshot.active_job_count == 2
    assert snapshot.updated_job_count == 1
    assert snapshot.distinct_company_count == 2
    assert snapshot.source_job_counts == {"careerviet": 2}


def test_creates_one_snapshot_for_each_eligible_family_and_location_membership() -> None:
    snapshots = JobFamilyTrendSnapshotBuilder().build(
        [
            make_fact(
                "multi-family",
                category_ids=["quality_assurance", "food_beverage"],
                family_ids=["operations", "people_services"],
                location_ids=["ha-noi", "ho-chi-minh"],
            )
        ],
        period_start=date(2026, 6, 15),
        period_end=date(2026, 6, 21),
    )

    assert {
        (snapshot.job_family_id, snapshot.location_id)
        for snapshot in snapshots
    } == {
        ("operations", "ha-noi"),
        ("operations", "ho-chi-minh"),
        ("people_services", "ha-noi"),
        ("people_services", "ho-chi-minh"),
    }


def make_fact(
    job_id: str,
    *,
    category_ids: list[str],
    family_ids: list[str],
    location_ids: list[str] | None = None,
    company_key: str = "company-a",
    source_updated_at: date | None = date(2026, 6, 17),
    source_expires_at: date | None = date(2026, 6, 30),
) -> JobCategoryTrendJobFact:
    return JobCategoryTrendJobFact(
        job_key=f"careerviet:{job_id}",
        source="careerviet",
        source_job_id=job_id,
        job_url=None,
        canonical_job_url=None,
        job_title="Example job",
        company=company_key,
        company_key=company_key,
        location_ids=location_ids or ["ho-chi-minh"],
        seniority=None,
        employment_type=None,
        source_updated_at=source_updated_at,
        source_expires_at=source_expires_at,
        is_active=None,
        content_hash=job_id,
        requirements_text=None,
        description_text=None,
        raw_job_category_labels=[],
        job_category_ids=category_ids,
        job_family_ids=family_ids,
        unmatched_job_category_labels=[],
        invalid_job_category_labels=[],
        taxonomy_version="job-category-taxonomy-v1",
    )
