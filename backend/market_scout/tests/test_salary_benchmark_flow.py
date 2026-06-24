from __future__ import annotations

from typing import Any

from backend.market_scout.flows.salary_benchmark_flow import SalaryBenchmarkFlow
from backend.market_scout.repositories.salary_benchmark.salary_vector_repository import SalaryVectorSearchResult
from backend.market_scout.schemas.salary_benchmark.salary import SalaryJobRecord
from backend.market_scout.services.salary_benchmark.salary_summary_service import SalarySummaryResult


class FakeVectorRepository:
    def __init__(self) -> None:
        self.kwargs: dict[str, Any] | None = None

    def search(self, query: str, **kwargs: Any) -> list[SalaryVectorSearchResult]:
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
