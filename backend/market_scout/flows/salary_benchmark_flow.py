from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from time import perf_counter
from typing import Any, Protocol

from backend.market_scout.repositories.salary_benchmark.salary_vector_repository import SalaryVectorRepository, SalaryVectorSearchResult
from backend.market_scout.services.salary_benchmark.salary_benchmark_service import SalaryBenchmarkResult, SalaryBenchmarkService
from backend.market_scout.services.salary_benchmark.salary_summary_service import SalarySummaryResult, SalarySummaryService

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
    ) -> None:
        self.vector_repository = vector_repository or SalaryVectorRepository()
        self.benchmark_service = benchmark_service or SalaryBenchmarkService()
        self.summary_service = summary_service or SalarySummaryService()

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
        search_start = perf_counter()
        search_results = self.vector_repository.search(
            query,
            top_k=top_k,
            fetch_k=fetch_k,
            require_salary=True,
            filter_location=filter_location,
            filter_experience=filter_experience,
            distance_threshold=distance_threshold,
        )
        _log_step("salary_vector_search", query, search_start, retrieved_records=len(search_results))

        aggregate_start = perf_counter()
        benchmark = self.benchmark_service.aggregate(query, search_results)
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
