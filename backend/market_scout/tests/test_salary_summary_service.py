from __future__ import annotations

import json
from typing import Any

from backend.market_scout.services.salary_benchmark.salary_benchmark_service import (
    SalaryBenchmarkResult,
    SalaryBenchmarkSource,
    SalaryRange,
)
from backend.market_scout.services.salary_benchmark.salary_summary_service import SalarySummaryService


class FakeResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLM:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.messages: list[Any] | None = None

    def invoke(self, input: Any, **kwargs: Any) -> FakeResponse:
        self.messages = input
        return FakeResponse(self.answer)


def make_benchmark() -> SalaryBenchmarkResult:
    return SalaryBenchmarkResult(
        job_title="Sales B2B",
        location="Ho Chi Minh",
        experience_years=2,
        salary_range=SalaryRange(min=12_000_000, max=17_000_000),
        sample_size=8,
        confidence="high",
        average_distance=0.14,
        sources=[
            SalaryBenchmarkSource(
                company="ABC",
                job_title="Sales Executive B2B",
                job_url="https://example.com/job",
                salary_min_vnd=12_000_000,
                salary_max_vnd=17_000_000,
                distance=0.14,
            )
        ],
    )


def test_salary_summary_service_invokes_llm_with_benchmark_payload() -> None:
    fake_llm = FakeLLM("Muc luong tham khao khoang 12 - 17 trieu VND/thang.")
    service = SalarySummaryService(llm=fake_llm, model_name="fake-gemini")

    summary = service.summarize("Luong Sales B2B o HCM", make_benchmark())

    assert summary.answer.startswith("Muc luong tham khao khoang 12 - 17 trieu VND/thang.")
    assert "Mot so JD lien quan ban co the tham khao:" in summary.answer
    assert "[ABC - Sales Executive B2B](https://example.com/job): 12 - 17 trieu VND/thang" in summary.answer
    assert summary.model_name == "fake-gemini"
    assert fake_llm.messages is not None
    payload = json.loads(fake_llm.messages[1].content)
    assert payload["user_query"] == "Luong Sales B2B o HCM"
    assert payload["benchmark"]["salary_range_text"] == "12 - 17 trieu VND/thang"
    assert payload["benchmark"]["confidence"] == "high"
    assert payload["instructions"]["do_not_recalculate_salary"] is True

def test_salary_summary_service_does_not_duplicate_job_links() -> None:
    answer = "Muc luong tham khao. Source: https://example.com/job"
    service = SalarySummaryService(llm=FakeLLM(answer), model_name="fake-gemini")

    summary = service.summarize("Luong Sales B2B o HCM", make_benchmark())

    assert summary.answer == answer
