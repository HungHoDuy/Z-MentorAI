from backend.market_scout.repositories.salary_vector_repository import SalaryVectorSearchResult
from backend.market_scout.schemas.salary import SalaryJobRecord
from backend.market_scout.services.salary_benchmark_service import SalaryBenchmarkService


def make_result(
    document_id: str,
    *,
    salary_min_vnd: int,
    salary_max_vnd: int,
    distance: float,
    job_title: str = "Sales Executive B2B",
) -> SalaryVectorSearchResult:
    record = SalaryJobRecord(
        job_id=document_id,
        job_url=f"https://example.com/{document_id}",
        company="ABC",
        job_title=job_title,
        locations=["Hồ Chí Minh"],
        salary_min_vnd=salary_min_vnd,
        salary_max_vnd=salary_max_vnd,
        min_experience=2,
        source_document_id=document_id,
    )
    return SalaryVectorSearchResult(record=record, distance=distance, embedding_text=None, raw_data={})


def test_salary_benchmark_service_averages_filtered_salary_ranges() -> None:
    service = SalaryBenchmarkService()
    results = [
        make_result("1", salary_min_vnd=10_000_000, salary_max_vnd=12_000_000, distance=0.11),
        make_result("2", salary_min_vnd=12_000_000, salary_max_vnd=14_000_000, distance=0.12),
        make_result("3", salary_min_vnd=14_000_000, salary_max_vnd=16_000_000, distance=0.13),
    ]

    benchmark = service.aggregate("Lương Sales B2B ở HCM với 2 năm kinh nghiệm", results)

    assert benchmark.salary_range is not None
    assert benchmark.salary_range.min == 12_000_000
    assert benchmark.salary_range.max == 14_000_000
    assert benchmark.sample_size == 3
    assert benchmark.confidence == "high"
    assert benchmark.average_distance == 0.12
    assert len(benchmark.sources) == 3


def test_salary_benchmark_service_removes_midpoint_outliers() -> None:
    service = SalaryBenchmarkService()
    results = [
        make_result("1", salary_min_vnd=10_000_000, salary_max_vnd=12_000_000, distance=0.11),
        make_result("2", salary_min_vnd=11_000_000, salary_max_vnd=13_000_000, distance=0.12),
        make_result("3", salary_min_vnd=12_000_000, salary_max_vnd=14_000_000, distance=0.13),
        make_result("4", salary_min_vnd=13_000_000, salary_max_vnd=15_000_000, distance=0.14),
        make_result("outlier", salary_min_vnd=200_000_000, salary_max_vnd=250_000_000, distance=0.15),
    ]

    benchmark = service.aggregate("Lương Sales B2B", results)

    assert benchmark.salary_range is not None
    assert benchmark.discarded_outliers == 1
    assert benchmark.sample_size == 4
    assert benchmark.salary_range.min == 11_500_000
    assert benchmark.salary_range.max == 13_500_000


def test_salary_benchmark_service_confidence_uses_vector_distance_not_sample_size() -> None:
    service = SalaryBenchmarkService()
    close_results = [
        make_result("1", salary_min_vnd=10_000_000, salary_max_vnd=12_000_000, distance=0.12),
        make_result("2", salary_min_vnd=12_000_000, salary_max_vnd=14_000_000, distance=0.14),
    ]
    far_results = [
        make_result("1", salary_min_vnd=10_000_000, salary_max_vnd=12_000_000, distance=0.42),
        make_result("2", salary_min_vnd=12_000_000, salary_max_vnd=14_000_000, distance=0.44),
    ]

    close_benchmark = service.aggregate("LÆ°Æ¡ng Sales B2B", close_results)
    far_benchmark = service.aggregate("LÆ°Æ¡ng Sales B2B", far_results)

    assert close_benchmark.sample_size == 2
    assert close_benchmark.confidence == "high"
    assert far_benchmark.sample_size == 2
    assert far_benchmark.confidence == "low"


def test_salary_benchmark_service_returns_empty_result_when_no_valid_salary() -> None:
    service = SalaryBenchmarkService()
    results = [
        make_result("bad", salary_min_vnd=0, salary_max_vnd=12_000_000, distance=0.1),
    ]

    benchmark = service.aggregate("Lương Sales B2B", results)

    assert benchmark.salary_range is None
    assert benchmark.sample_size == 0
    assert benchmark.confidence == "low"
