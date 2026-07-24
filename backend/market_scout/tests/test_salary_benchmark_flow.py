from __future__ import annotations

from typing import Any

from backend.market_scout.flows.salary_benchmark_flow import SalaryBenchmarkFlow
from backend.market_scout.repositories.salary_benchmark.salary_vector_repository import SalaryVectorSearchResult
from backend.market_scout.schemas.salary_benchmark.salary import SalaryJobRecord, SalarySearchQuery
from backend.market_scout.services.salary_benchmark.salary_summary_service import SalarySummaryResult


class FakeQueryUnderstandingService:
    def __init__(self, parsed_query: SalarySearchQuery | None = None) -> None:
        self.parsed_query = parsed_query
        self.calls: list[str] = []

    def extract(self, user_query: str) -> SalarySearchQuery:
        self.calls.append(user_query)
        if self.parsed_query is not None:
            return self.parsed_query
        return SalarySearchQuery(raw_query=user_query, job_title="Sales B2B", job_title_normalized="sales b2b")


class FakeVectorRepository:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None
        self.calls = 0

    def search(self, query: str, **kwargs: Any) -> list[SalaryVectorSearchResult]:
        self.calls += 1
        self.kwargs = kwargs
        return [
            _make_result("1", 10_000_000, 12_000_000, 0.11),
            _make_result("2", 12_000_000, 14_000_000, 0.12),
        ]


class FakeSummaryService:
    def __init__(self) -> None:
        self.query: str | None = None

    def summarize(self, user_query: str, benchmark: Any) -> SalarySummaryResult:
        self.query = user_query
        return SalarySummaryResult(
            answer="Muc luong tham khao khoang 11 - 13 trieu VND/thang.",
            model_name="fake-gemini",
        )


def test_salary_benchmark_flow_runs_search_aggregate_and_llm_summary() -> None:
    vector_repository = FakeVectorRepository()
    summary_service = FakeSummaryService()
    flow = SalaryBenchmarkFlow(
        vector_repository=vector_repository,
        summary_service=summary_service,
        query_understanding_service=FakeQueryUnderstandingService(),
    )

    result = flow.run(
        "Luong Sales B2B o HCM",
        top_k=2,
        fetch_k=10,
        distance_threshold=0.3,
    )

    assert result.retrieved_records == 2
    assert result.answer == "Muc luong tham khao khoang 11 - 13 trieu VND/thang."
    assert result.benchmark.salary_range is not None
    assert result.benchmark.salary_range.min == 11_000_000
    assert result.benchmark.salary_range.max == 13_000_000
    assert result.benchmark.confidence == "high"
    assert summary_service.query == "Luong Sales B2B o HCM"
    assert vector_repository.kwargs == {
        "top_k": 2,
        "fetch_k": 10,
        "require_salary": True,
        "filter_location": True,
        "filter_experience": True,
        "distance_threshold": 0.3,
    }


def test_salary_benchmark_flow_asks_for_job_when_query_has_only_location_and_experience() -> None:
    vector_repository = FakeVectorRepository()
    summary_service = FakeSummaryService()
    flow = SalaryBenchmarkFlow(
        vector_repository=vector_repository,
        summary_service=summary_service,
        query_understanding_service=FakeQueryUnderstandingService(
            SalarySearchQuery(
                raw_query="Toi co 3 nam kinh nghiem o Ha Noi, luong bao nhieu?",
                job_title=None,
                job_title_normalized=None,
                location="Ha Noi",
                location_normalized="ha noi",
                experience_years=3,
            )
        ),
    )

    result = flow.run("Toi co 3 nam kinh nghiem o Ha Noi, luong bao nhieu?")

    assert result.retrieved_records == 0
    assert result.benchmark.salary_range is None
    assert result.benchmark.job_title is None
    assert result.benchmark.experience_years == 3
    assert "vi tri cong viec cu the" in result.answer
    assert vector_repository.calls == 0
    assert summary_service.query is None


def _make_result(
    document_id: str,
    salary_min_vnd: int,
    salary_max_vnd: int,
    distance: float,
) -> SalaryVectorSearchResult:
    record = SalaryJobRecord(
        job_id=document_id,
        job_url=f"https://example.com/{document_id}",
        company="ABC",
        job_title="Sales Executive B2B",
        locations=["Ho Chi Minh"],
        salary_min_vnd=salary_min_vnd,
        salary_max_vnd=salary_max_vnd,
        min_experience=2,
        source_document_id=document_id,
    )
    return SalaryVectorSearchResult(record=record, distance=distance, embedding_text=None, raw_data={})
