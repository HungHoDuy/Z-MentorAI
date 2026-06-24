from datetime import date

from backend.market_scout.schemas.trend_tracker.job_category_trend import JobCategoryTrendJobFact
from backend.market_scout.schemas.trend_tracker.job_family_trend_snapshot import JobFamilyTrendSnapshot
from backend.market_scout.services.trend_tracker.skill_frequency_service import SkillFrequencyService


class FakeFactRepository:
    def __init__(self, facts: list[JobCategoryTrendJobFact]) -> None:
        self.facts = facts
        self.last_category_id: str | None = None

    def list_active_for_snapshot(
        self,
        snapshot: JobFamilyTrendSnapshot,
        *,
        job_category_id: str | None = None,
    ) -> list[JobCategoryTrendJobFact]:
        self.last_category_id = job_category_id
        return self.facts


def test_counts_each_skill_once_per_fact_and_calculates_share() -> None:
    repository = FakeFactRepository(
        [
            make_fact("1", "Excel, IFRS, Excel", "SAP experience"),
            make_fact("2", "Excel and English", "IFRS reporting"),
            make_fact("3", "English", ""),
        ]
    )
    signal = SkillFrequencyService(
        fact_repository=repository,
        min_sample_size=3,
    ).evaluate(make_snapshot(), top_k=10)

    assert signal.signal == "current_skill_demand"
    assert signal.sample_size == 3
    assert [(skill.skill_id, skill.job_count, skill.job_share) for skill in signal.skills] == [
        ("english", 2, 0.6667),
        ("excel", 2, 0.6667),
        ("ifrs", 2, 0.6667),
        ("sap", 1, 0.3333),
    ]


def test_returns_insufficient_evidence_for_small_cohort() -> None:
    signal = SkillFrequencyService(
        fact_repository=FakeFactRepository([make_fact("1", "Excel", "")]),
        min_sample_size=2,
    ).evaluate(make_snapshot())

    assert signal.signal == "insufficient_evidence"
    assert signal.sample_size == 1
    assert signal.skills == []


def make_snapshot() -> JobFamilyTrendSnapshot:
    return JobFamilyTrendSnapshot(
        period="2026-W25",
        period_start=date(2026, 6, 15),
        period_end=date(2026, 6, 21),
        job_family_id="finance_legal",
        location_id="hai-duong",
        observed_job_count=3,
        active_job_count=3,
        unknown_active_job_count=0,
        updated_job_count=0,
        distinct_company_count=3,
        source_job_counts={"careerviet": 3},
        taxonomy_version="job-category-taxonomy-v1",
    )


def make_fact(job_id: str, requirements: str, description: str) -> JobCategoryTrendJobFact:
    return JobCategoryTrendJobFact(
        job_key=f"careerviet:{job_id}",
        source="careerviet",
        source_job_id=job_id,
        job_url=None,
        canonical_job_url=None,
        job_title="Finance Analyst",
        company="Example Company",
        company_key="example-company",
        location_ids=["hai-duong"],
        seniority=None,
        employment_type=None,
        source_updated_at=date(2026, 6, 17),
        source_expires_at=date(2026, 6, 30),
        is_active=True,
        content_hash=job_id,
        requirements_text=requirements,
        description_text=description,
        raw_job_category_labels=["Tài chính / Đầu tư"],
        job_category_ids=["finance_investment"],
        job_family_ids=["finance_legal"],
        unmatched_job_category_labels=[],
        invalid_job_category_labels=[],
        taxonomy_version="job-category-taxonomy-v1",
    )
