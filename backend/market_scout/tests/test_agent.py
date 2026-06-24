from __future__ import annotations

import asyncio
from typing import Any

from backend.market_scout.agent import MarketScoutAgent
from backend.market_scout.flows.salary_benchmark_flow import SalaryBenchmarkFlowResult
from backend.market_scout.schemas import MarketScoutIntent
from backend.market_scout.services.salary_benchmark_service import (
    SalaryBenchmarkResult,
    SalaryBenchmarkSource,
    SalaryRange,
)
from backend.market_scout.services.salary_summary_service import SalarySummaryResult


class FakeSalaryFlow:
    def __init__(self, result: SalaryBenchmarkFlowResult) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def run(self, query: str, **kwargs: Any) -> SalaryBenchmarkFlowResult:
        self.calls.append((query, kwargs))
        return self.result


def test_market_scout_agent_routes_salary_query_to_salary_flow() -> None:
    flow_result = _make_flow_result()
    salary_flow = FakeSalaryFlow(flow_result)
    agent = MarketScoutAgent(salary_flow=salary_flow, default_top_k=5, default_fetch_k=10)

    response = asyncio.run(agent.run("Luong Sales B2B o Ho Chi Minh"))

    assert response.intent == MarketScoutIntent.SALARY_BENCHMARK
    assert response.answer == "Muc luong tham khao khoang 12 - 17 trieu VND/thang."
    assert response.confidence == "high"
    assert response.data["salary_range"] == {
        "min": 12_000_000,
        "max": 17_000_000,
        "currency": "VND",
        "period": "monthly",
    }
    assert response.sources[0]["job_url"] == "https://example.com/job"
    assert response.limitations == []
    assert response.to_dict()["intent"] == "salary_benchmark"
    assert salary_flow.calls == [
        (
            "Luong Sales B2B o Ho Chi Minh",
            {
                "top_k": 5,
                "fetch_k": 10,
            },
        )
    ]


def test_market_scout_agent_asks_for_trend_entities_when_query_is_ambiguous() -> None:
    salary_flow = FakeSalaryFlow(_make_flow_result())
    agent = MarketScoutAgent(salary_flow=salary_flow)

    response = asyncio.run(agent.run("Xu huong AI Data tai Vietnam 2026"))

    assert response.intent == MarketScoutIntent.TREND_TRACKER
    assert response.confidence == "low"
    assert "Vui long cung cap job category" in response.answer
    assert salary_flow.calls == []


def _make_flow_result() -> SalaryBenchmarkFlowResult:
    benchmark = SalaryBenchmarkResult(
        job_title="Sales B2B",
        location="Ho Chi Minh",
        experience_years=2,
        salary_range=SalaryRange(min=12_000_000, max=17_000_000),
        sample_size=4,
        confidence="high",
        sources=[
            SalaryBenchmarkSource(
                company="ABC",
                job_title="Sales Executive B2B",
                job_url="https://example.com/job",
                salary_min_vnd=12_000_000,
                salary_max_vnd=17_000_000,
                distance=0.12,
            )
        ],
        average_distance=0.12,
        matched_records=4,
    )
    summary = SalarySummaryResult(
        answer="Muc luong tham khao khoang 12 - 17 trieu VND/thang.",
        model_name="fake-gemini",
    )
    return SalaryBenchmarkFlowResult(
        query="Luong Sales B2B o Ho Chi Minh",
        retrieved_records=4,
        benchmark=benchmark,
        summary=summary,
    )
