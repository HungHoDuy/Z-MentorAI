from __future__ import annotations

from dataclasses import dataclass

from backend.market_scout.schemas.salary_benchmark.salary import SalaryJobRecord, SalarySearchQuery
from backend.market_scout.services.salary_benchmark.salary_benchmark_service import SalaryBenchmarkService


@dataclass(frozen=True)
class FakeSearchResult:
    record: SalaryJobRecord
    distance: float | None


def make_record(company: str, title: str, url: str, salary_min: int, salary_max: int) -> SalaryJobRecord:
    return SalaryJobRecord(
        job_id=url.rsplit("/", 1)[-1],
        job_url=url,
        company=company,
        job_title=title,
        locations=["Ha Noi"],
        salary_min_vnd=salary_min,
        salary_max_vnd=salary_max,
        min_experience=2,
    )


def test_salary_sources_are_deduped_by_company_and_title() -> None:
    service = SalaryBenchmarkService(source_limit=5)
    query = SalarySearchQuery(raw_query="AI Engineer salary", job_title="AI Engineer")
    results = [
        FakeSearchResult(
            make_record("CANIFA", "AI Engineer", "https://example.com/canifa-1", 16_000_000, 35_000_000),
            0.10,
        ),
        FakeSearchResult(
            make_record("CANIFA", "AI Engineer", "https://example.com/canifa-2", 16_000_000, 35_000_000),
            0.11,
        ),
        FakeSearchResult(
            make_record("FOXAI", "AI Engineer", "https://example.com/foxai", 20_000_000, 30_000_000),
            0.12,
        ),
        FakeSearchResult(
            make_record("Viettel", "AI Engineer", "https://example.com/viettel", 18_000_000, 29_000_000),
            0.13,
        ),
    ]

    benchmark = service.aggregate(query, results)

    source_labels = [(source.company, source.job_title) for source in benchmark.sources]
    assert source_labels == [
        ("CANIFA", "AI Engineer"),
        ("FOXAI", "AI Engineer"),
        ("Viettel", "AI Engineer"),
    ]
    assert benchmark.sample_size == 4

def test_salary_range_uses_p25_min_and_p75_max() -> None:
    service = SalaryBenchmarkService()
    query = SalarySearchQuery(raw_query="Backend salary", job_title="Backend Engineer")
    results = [
        FakeSearchResult(
            make_record("A", "Backend Engineer", "https://example.com/a", 10_000_000, 20_000_000),
            0.10,
        ),
        FakeSearchResult(
            make_record("B", "Backend Engineer", "https://example.com/b", 20_000_000, 30_000_000),
            0.11,
        ),
        FakeSearchResult(
            make_record("C", "Backend Engineer", "https://example.com/c", 30_000_000, 40_000_000),
            0.12,
        ),
        FakeSearchResult(
            make_record("D", "Backend Engineer", "https://example.com/d", 40_000_000, 50_000_000),
            0.13,
        ),
    ]

    benchmark = service.aggregate(query, results)

    assert benchmark.salary_range is not None
    assert benchmark.salary_range.min == 17_500_000
    assert benchmark.salary_range.max == 42_500_000
    assert benchmark.sample_size == 4
