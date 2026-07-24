from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from time import perf_counter
from typing import Any, Protocol

from backend.market_scout.repositories.salary_benchmark.salary_vector_repository import SalaryVectorRepository, SalaryVectorSearchResult
from backend.market_scout.services.salary_benchmark.salary_benchmark_service import SalaryBenchmarkResult, SalaryBenchmarkService
from backend.market_scout.services.salary_benchmark.salary_summary_service import SalarySummaryResult, SalarySummaryService
from backend.market_scout.services.salary_benchmark.salary_query_understanding_service import SalaryQueryUnderstandingService

logger = logging.getLogger("market_scout")


def _log_step(step: str, query: str, start: float, **fields: Any) -> None:
    logger.info(
        json.dumps(
            {
                "event": "market_scout_step",
                "agent": "market_scout",
                "sub_agent": "salary_benchmark",
                "step": step,
                "duration_ms": round((perf_counter() - start) * 1000, 2),
                "user_query": " ".join(query.split())[:500],
                **fields,
            },
            ensure_ascii=False,
            default=str,
        )
    )

class SalaryVectorSearchPort(Protocol):
    def search(
        self,
        query: str,
        *,
        top_k: int,
        fetch_k: int | None,
        require_salary: bool,
        filter_location: bool,
        filter_experience: bool,
        distance_threshold: float | None,
    ) -> list[SalaryVectorSearchResult]:
        ...


@dataclass(frozen=True)
class SalaryBenchmarkFlowResult:
    query: str
    retrieved_records: int
    benchmark: SalaryBenchmarkResult
    summary: SalarySummaryResult

    @property
    def answer(self) -> str:
        return self.summary.answer

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "retrieved_records": self.retrieved_records,
            "answer": self.answer,
            "summary": self.summary.to_dict(),
            "benchmark": self.benchmark.to_dict(),
        }


class SalaryBenchmarkFlow:
    """Run salary vector retrieval, deterministic aggregation, and LLM summary."""

    def __init__(
        self,
        *,
        vector_repository: SalaryVectorSearchPort | None = None,
        benchmark_service: SalaryBenchmarkService | None = None,
        summary_service: SalarySummaryService | None = None,
        query_understanding_service: SalaryQueryUnderstandingService | None = None,
    ) -> None:
        self.vector_repository = vector_repository or SalaryVectorRepository()
        self.benchmark_service = benchmark_service or SalaryBenchmarkService()
        self.summary_service = summary_service or SalarySummaryService()
        self.query_understanding_service = query_understanding_service or SalaryQueryUnderstandingService(
            normalizer=self.benchmark_service.normalizer
        )

    def run(
        self,
        query: str,
        *,
        top_k: int = 30,
        fetch_k: int | None = 80,
        distance_threshold: float | None = None,
        filter_location: bool = True,
        filter_experience: bool = True,
    ) -> SalaryBenchmarkFlowResult:
        search_query = self.query_understanding_service.extract(query)
        if not search_query.job_title_normalized:
            benchmark = SalaryBenchmarkResult(
                job_title=None,
                location=search_query.location,
                experience_years=search_query.experience_years,
                salary_range=None,
                sample_size=0,
                confidence="low",
                sources=[],
                average_distance=None,
                discarded_outliers=0,
                matched_records=0,
            )
            return SalaryBenchmarkFlowResult(
                query=query,
                retrieved_records=0,
                benchmark=benchmark,
                summary=SalarySummaryResult(
                    answer=(
                        "Minh can ban cho biet vi tri cong viec cu the de tra cuu muc luong. "
                        "Ban co the hoi kieu: luong Business Analyst tai Ha Noi voi 3 nam kinh nghiem la bao nhieu?"
                    ),
                    model_name="salary-rule-based-clarification",
                ),
            )

        search_start = perf_counter()
        search_results = self.vector_repository.search(
            search_query,
            top_k=top_k,
            fetch_k=fetch_k,
            require_salary=True,
            filter_location=filter_location,
            filter_experience=filter_experience,
            distance_threshold=distance_threshold,
        )
        _log_step("salary_vector_search", query, search_start, retrieved_records=len(search_results))

        aggregate_start = perf_counter()
        benchmark = self.benchmark_service.aggregate(search_query, search_results)
        _log_step(
            "salary_aggregate",
            query,
            aggregate_start,
            sample_size=benchmark.sample_size,
            confidence=benchmark.confidence,
        )

        summary_start = perf_counter()
        summary = self.summary_service.summarize(query, benchmark)
        _log_step("salary_summary", query, summary_start, model_name=summary.model_name)
        return SalaryBenchmarkFlowResult(
            query=query,
            retrieved_records=len(search_results),
            benchmark=benchmark,
            summary=summary,
        )
