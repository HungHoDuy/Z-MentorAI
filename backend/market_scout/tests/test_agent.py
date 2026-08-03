from __future__ import annotations

import asyncio
from typing import Any

from backend.market_scout.agent import MarketScoutAgent, _classify_intent, _trend_intent_from_query
from backend.market_scout.flows.salary_benchmark_flow import SalaryBenchmarkFlowResult
from backend.market_scout.flows.trend_tracker_flow import TrendTrackerFlowResult
from backend.market_scout.schemas import MarketScoutIntent, MarketScoutRequest
from backend.market_scout.schemas.market_scout_query_understanding import (
    MarketScoutQueryUnderstanding,
    TrendQueryUnderstanding,
)
from backend.market_scout.schemas.trend_tracker.hybrid_signal import HybridSignalResult
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery, TrendQueryIntent
from backend.market_scout.schemas.trend_tracker.trend_summary import TrendSummaryResult
from backend.market_scout.services.salary_benchmark.salary_benchmark_service import (
    SalaryBenchmarkResult,
    SalaryBenchmarkSource,
    SalaryRange,
)
from backend.market_scout.services.salary_benchmark.salary_summary_service import SalarySummaryResult


class FakeSalaryFlow:
    def __init__(self, result: SalaryBenchmarkFlowResult) -> None:
        self.result = result
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def run(self, query: str, **kwargs: Any) -> SalaryBenchmarkFlowResult:
        self.calls.append((query, kwargs))
        return self.result




class FakeTrendSummaryComposer:
    def __init__(self) -> None:
        self.calls = []

    def summarize(self, result: TrendTrackerFlowResult) -> TrendSummaryResult:
        self.calls.append(result)
        return TrendSummaryResult(
            answer="Trend response.",
            confidence=result.signal.confidence,
            sources=result.signal.sources,
            limitations=result.signal.limitations,
            composer_version="fake",
        )

class FakeTrendFlow:
    def __init__(self) -> None:
        self.calls = []

    def run(self, query_input):
        self.calls.append(query_input)
        query = TrendQuery(
            intent=query_input.intent,
            job_family_id=query_input.job_family_id or "digital_telecom",
            job_category_id=query_input.job_category_id,
            location_id=query_input.location_id or "ha-noi",
            role_mention=query_input.role_mention,
        )
        return TrendTrackerFlowResult(
            query=query,
            signal=HybridSignalResult(
                intent=query.intent.value,
                signal="current_role_demand_limited",
                job_family_id=query.job_family_id,
                job_category_id=query.job_category_id,
                location_id=query.location_id,
                snapshot_id=None,
                period=None,
                confidence="low",
                directional_trend=False,
                data={"active_job_count": 3, "distinct_company_count": 2},
                sources=[],
                limitations=[],
            ),
        )


class FakeQueryUnderstandingService:
    def __init__(self, trend_query: TrendQueryUnderstanding | None = None) -> None:
        self.trend_query = trend_query
        self.calls: list[str] = []

    def understand(self, user_query: str) -> MarketScoutQueryUnderstanding:
        self.calls.append(user_query)
        return MarketScoutQueryUnderstanding(
            intent=MarketScoutIntent.TREND_TRACKER,
            trend_query=self.trend_query,
            confidence="high" if self.trend_query else "low",
            source="fake",
        )

class FakeIntentClassifier:
    def __init__(self, intent: MarketScoutIntent) -> None:
        self.intent = intent
        self.calls: list[str] = []

    def classify(self, user_query: str) -> str:
        self.calls.append(user_query)
        return self.intent.value


def test_market_scout_agent_routes_salary_query_to_salary_flow() -> None:
    flow_result = _make_flow_result()
    salary_flow = FakeSalaryFlow(flow_result)
    agent = MarketScoutAgent(
        salary_flow=salary_flow,
        intent_classifier=FakeIntentClassifier(MarketScoutIntent.SALARY_BENCHMARK),
        default_top_k=5,
        default_fetch_k=10,
    )

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


def test_market_scout_agent_routes_trend_query_to_trend_tracker() -> None:
    salary_flow = FakeSalaryFlow(_make_flow_result())
    trend_flow = FakeTrendFlow()
    agent = MarketScoutAgent(
        salary_flow=salary_flow,
        trend_flow=trend_flow,
        response_composer=FakeTrendSummaryComposer(),
        query_understanding_service=FakeQueryUnderstandingService(),
    )

    response = asyncio.run(agent.run("Xu huong AI Data tai Vietnam 2026"))

    assert response.intent == MarketScoutIntent.TREND_TRACKER
    assert response.confidence == "low"
    assert salary_flow.calls == []
    assert len(trend_flow.calls) == 1


def test_market_scout_agent_extracts_role_mention_from_query_understanding_for_ui_query() -> None:
    trend_flow = FakeTrendFlow()
    query_understanding = FakeQueryUnderstandingService(
        TrendQueryUnderstanding(
            intent=TrendQueryIntent.CURRENT_DEMAND,
            role_mention="business analyst",
            location_text="Ha Noi",
            confidence="high",
        )
    )
    agent = MarketScoutAgent(
        salary_flow=FakeSalaryFlow(_make_flow_result()),
        trend_flow=trend_flow,
        response_composer=FakeTrendSummaryComposer(),
        query_understanding_service=query_understanding,
    )

    response = asyncio.run(agent.run("business analyst tai Ha Noi co dang tuyen nhieu khong?"))

    assert response.intent == MarketScoutIntent.TREND_TRACKER
    assert query_understanding.calls == ["business analyst tai Ha Noi co dang tuyen nhieu khong?"]
    assert trend_flow.calls[0].role_mention == "business analyst"
    assert trend_flow.calls[0].location_id == "ha-noi"


def test_market_scout_agent_classifies_hiring_volume_question_as_trend_tracker() -> None:
    query = "vi tri DevOps tai Ho Chi Minh co tuyen dung nhieu khong?"

    assert _classify_intent(query) is MarketScoutIntent.TREND_TRACKER


def test_market_scout_agent_classifies_skill_questions_as_trend_tracker() -> None:
    query = "Nganh kinh doanh ban hang tai Ho Chi Minh dang can ky nang gi?"

    assert _classify_intent(query) is MarketScoutIntent.TREND_TRACKER
    assert _trend_intent_from_query(query) == TrendQueryIntent.CURRENT_SKILL_DEMAND.value



def test_market_scout_agent_classifies_external_outlook_question_as_trend_tracker() -> None:
    query = "Sales va marketing nam 2026 con trien vong khong?"

    assert _classify_intent(query) is MarketScoutIntent.TREND_TRACKER
    assert _trend_intent_from_query(query) == TrendQueryIntent.EXTERNAL_OUTLOOK.value


def test_market_scout_agent_classifies_future_development_question_as_external_outlook() -> None:
    query = "Software AI Data trong vai nam toi co con phat trien khong?"

    assert _classify_intent(query) is MarketScoutIntent.TREND_TRACKER
    assert _trend_intent_from_query(query) == TrendQueryIntent.EXTERNAL_OUTLOOK.value

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

def test_market_scout_agent_uses_cv_context_for_salary_query() -> None:
    flow_result = _make_flow_result()
    salary_flow = FakeSalaryFlow(flow_result)
    agent = MarketScoutAgent(salary_flow=salary_flow, default_top_k=5, default_fetch_k=10)

    response = asyncio.run(
        agent.run(
            MarketScoutRequest(
                user_query="Voi CV nay thi thi truong tra muc luong bao nhieu?",
                intent_hint=MarketScoutIntent.SALARY_BENCHMARK,
                user_context={
                    "profile_analysis": {"target_role": "Business Analyst"},
                    "location": "Ha Noi",
                    "seniority": "junior",
                },
            )
        )
    )

    enriched_query = salary_flow.calls[0][0]
    assert response.intent == MarketScoutIntent.SALARY_BENCHMARK
    assert "vi tri Business Analyst" in enriched_query
    assert "tai Ha Noi" in enriched_query
    assert "2 nam kinh nghiem" in enriched_query

def test_market_scout_agent_classifies_upcoming_ai_hiring_question_as_external_outlook() -> None:
    query = "nhu c\u1ea7u tuy\u1ec3n nh\u00e2n l\u1ef1c cho ng\u00e0nh AI s\u1eafp t\u1edbi nh\u01b0 th\u1ebf n\u00e0o?"

    assert _classify_intent(query) is MarketScoutIntent.TREND_TRACKER
    assert _trend_intent_from_query(query) == TrendQueryIntent.EXTERNAL_OUTLOOK.value


def test_market_scout_agent_overrides_llm_current_demand_when_query_has_future_signal() -> None:
    trend_flow = FakeTrendFlow()
    query_understanding = FakeQueryUnderstandingService(
        TrendQueryUnderstanding(
            intent=TrendQueryIntent.CURRENT_DEMAND,
            job_category_hint="AI",
            confidence="medium",
        )
    )
    agent = MarketScoutAgent(
        salary_flow=FakeSalaryFlow(_make_flow_result()),
        trend_flow=trend_flow,
        response_composer=FakeTrendSummaryComposer(),
        query_understanding_service=query_understanding,
    )

    response = asyncio.run(agent.run("nhu c\u1ea7u tuy\u1ec3n nh\u00e2n l\u1ef1c cho ng\u00e0nh AI s\u1eafp t\u1edbi nh\u01b0 th\u1ebf n\u00e0o?"))

    assert response.intent == MarketScoutIntent.TREND_TRACKER
    assert trend_flow.calls[0].intent == TrendQueryIntent.EXTERNAL_OUTLOOK
    assert trend_flow.calls[0].job_family_id == "digital_telecom"
    assert trend_flow.calls[0].location_id == "vietnam"
