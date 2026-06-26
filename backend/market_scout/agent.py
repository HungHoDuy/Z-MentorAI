from __future__ import annotations

import inspect
import json
import logging
from time import perf_counter
from typing import Any

from backend.market_scout.flows.salary_benchmark_flow import SalaryBenchmarkFlow, SalaryBenchmarkFlowResult
from backend.market_scout.flows.trend_tracker_flow import TrendTrackerFlow, TrendTrackerFlowResult
from backend.market_scout.schemas import MarketScoutIntent, MarketScoutRequest, MarketScoutResponse
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQueryInput, TrendQueryIntent
from backend.market_scout.services.trend_tracker.trend_llm_summary_service import TrendLlmSummaryService

logger = logging.getLogger("market_scout")


def _log_event(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


def _duration_ms(start: float) -> float:
    return round((perf_counter() - start) * 1000, 2)


def _short_query(query: str, max_length: int = 500) -> str:
    text = " ".join(query.split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."

class MarketScoutAgent:
    def __init__(
        self,
        intent_classifier: Any | None = None,
        entity_extractor: Any | None = None,
        query_planner: Any | None = None,
        salary_flow: SalaryBenchmarkFlow | None = None,
        trend_flow: Any | None = None,
        hybrid_flow: Any | None = None,
        response_composer: Any | None = None,
        default_top_k: int = 30,
        default_fetch_k: int | None = 80,
    ) -> None:
        self.intent_classifier = intent_classifier
        self.entity_extractor = entity_extractor
        self.query_planner = query_planner
        self.salary_flow = salary_flow
        self.trend_flow = trend_flow
        self.hybrid_flow = hybrid_flow
        self.response_composer = response_composer or TrendLlmSummaryService()
        self.default_top_k = default_top_k
        self.default_fetch_k = default_fetch_k

    async def run(self, request: MarketScoutRequest | str, user_context: dict[str, Any] | None = None) -> MarketScoutResponse:
        request_start = perf_counter()
        if isinstance(request, str):
            request = MarketScoutRequest(user_query=request, user_context=user_context or {})

        _log_event(
            "market_scout_request_start",
            agent="market_scout",
            user_query=_short_query(request.user_query),
            intent_hint=str(request.intent_hint) if request.intent_hint is not None else None,
        )
        intent_start = perf_counter()
        intent = await self._resolve_intent(request)
        _log_event(
            "market_scout_step",
            agent="market_scout",
            sub_agent=intent.value,
            step="resolve_intent",
            duration_ms=_duration_ms(intent_start),
            user_query=_short_query(request.user_query),
        )

        if intent == MarketScoutIntent.SALARY_BENCHMARK:
            salary_flow = self.salary_flow or SalaryBenchmarkFlow()
            flow_start = perf_counter()
            result = salary_flow.run(
                request.user_query,
                top_k=self.default_top_k,
                fetch_k=self.default_fetch_k,
            )
            _log_event(
                "market_scout_step",
                agent="market_scout",
                sub_agent="salary_benchmark",
                step="salary_flow_total",
                duration_ms=_duration_ms(flow_start),
                user_query=_short_query(request.user_query),
            )
            response = self._compose_salary_response(result)
            _log_event(
                "market_scout_request_end",
                agent="market_scout",
                sub_agent="salary_benchmark",
                confidence=response.confidence,
                duration_ms=_duration_ms(request_start),
                user_query=_short_query(request.user_query),
            )
            return response

        if intent in {
            MarketScoutIntent.TREND_TRACKER,
            MarketScoutIntent.JOB_DEMAND_FORECAST,
            MarketScoutIntent.INDUSTRY_DECLINE_RISK,
        }:
            response = await self._run_trend(request, intent)
            _log_event(
                "market_scout_request_end",
                agent="market_scout",
                sub_agent=intent.value,
                confidence=response.confidence,
                duration_ms=_duration_ms(request_start),
                user_query=_short_query(request.user_query),
            )
            return response

        if intent is MarketScoutIntent.MIXED:
            response = self._compose_unsupported_response(intent)
        else:
            response = self._compose_clarification_response()

        _log_event(
            "market_scout_request_end",
            agent="market_scout",
            sub_agent=intent.value,
            confidence=response.confidence,
            duration_ms=_duration_ms(request_start),
            user_query=_short_query(request.user_query),
        )
        return response
    async def _resolve_intent(self, request: MarketScoutRequest) -> MarketScoutIntent:
        if request.intent_hint is not None:
            return MarketScoutIntent.from_value(request.intent_hint)

        if self.intent_classifier is not None:
            raw_intent = self.intent_classifier.classify(request.user_query)
            raw_intent = await _maybe_await(raw_intent)
            return MarketScoutIntent.from_value(raw_intent)

        return _classify_intent(request.user_query)

    @staticmethod
    def _compose_salary_response(result: SalaryBenchmarkFlowResult) -> MarketScoutResponse:
        benchmark = result.benchmark
        limitations = _salary_limitations(result)
        return MarketScoutResponse(
            agent="market_scout",
            intent=MarketScoutIntent.SALARY_BENCHMARK,
            answer=result.answer,
            confidence=benchmark.confidence,
            data={
                "job_title": benchmark.job_title,
                "location": benchmark.location,
                "experience_years": benchmark.experience_years,
                "salary_range": benchmark.salary_range.to_dict() if benchmark.salary_range else None,
                "sample_size": benchmark.sample_size,
                "retrieved_records": result.retrieved_records,
                "matched_records": benchmark.matched_records,
                "discarded_outliers": benchmark.discarded_outliers,
                "average_distance": round(benchmark.average_distance, 4)
                if benchmark.average_distance is not None
                else None,
            },
            sources=[source.to_dict() for source in benchmark.sources],
            limitations=limitations,
        )

    async def _run_trend(
        self,
        request: MarketScoutRequest,
        market_intent: MarketScoutIntent,
    ) -> MarketScoutResponse:
        try:
            input_start = perf_counter()
            trend_input = await self._trend_query_input(request, market_intent)
            _log_event(
                "market_scout_step",
                agent="market_scout",
                sub_agent=market_intent.value,
                step="trend_build_query_input",
                duration_ms=_duration_ms(input_start),
                user_query=_short_query(request.user_query),
            )
            flow_start = perf_counter()
            trend_flow = self.trend_flow or TrendTrackerFlow()
            flow_result = trend_flow.run(trend_input)
            _log_event(
                "market_scout_step",
                agent="market_scout",
                sub_agent=market_intent.value,
                step="trend_flow_total",
                duration_ms=_duration_ms(flow_start),
                user_query=_short_query(request.user_query),
            )
        except ValueError as exc:
            return self._compose_trend_clarification_response(market_intent, str(exc))

        summary_start = perf_counter()
        summary = self.response_composer.summarize(flow_result)
        _log_event(
            "market_scout_step",
            agent="market_scout",
            sub_agent=market_intent.value,
            step="trend_summary",
            duration_ms=_duration_ms(summary_start),
            user_query=_short_query(request.user_query),
        )
        return self._compose_trend_response(market_intent, flow_result, summary)
    async def _trend_query_input(
        self,
        request: MarketScoutRequest,
        market_intent: MarketScoutIntent,
    ) -> TrendQueryInput:
        entities = await self._trend_entities(request)
        return TrendQueryInput(
            intent=_trend_intent_or_default(entities.get("trend_intent"), market_intent),
            job_family_id=_text_or_none(entities.get("job_family_id")),
            job_category_id=_text_or_none(entities.get("job_category_id")),
            job_category=_text_or_none(entities.get("job_category")),
            location_id=_text_or_none(entities.get("location_id")),
            location=_text_or_none(entities.get("location")),
        )

    async def _trend_entities(self, request: MarketScoutRequest) -> dict[str, Any]:
        entities: dict[str, Any] = {
            key: request.user_context[key]
            for key in _TREND_ENTITY_FIELDS
            if key in request.user_context
        }
        context_trend = request.user_context.get("trend")
        if isinstance(context_trend, dict):
            entities.update(context_trend)
        if request.entities_hint:
            entities.update(request.entities_hint)
        if self.entity_extractor is not None:
            try:
                extracted = self.entity_extractor.extract(request.user_query, request.user_context)
            except TypeError:
                extracted = self.entity_extractor.extract(request.user_query)
            extracted = await _maybe_await(extracted)
            if isinstance(extracted, dict):
                entities.update({key: value for key, value in extracted.items() if value is not None})
        return entities

    @staticmethod
    def _compose_trend_response(
        intent: MarketScoutIntent,
        flow_result: TrendTrackerFlowResult,
        summary: Any,
    ) -> MarketScoutResponse:
        return MarketScoutResponse(
            agent="market_scout",
            intent=intent,
            answer=summary.answer,
            confidence=summary.confidence,
            data={**flow_result.to_dict(), "summary": summary.to_dict()},
            sources=summary.sources,
            limitations=summary.limitations,
        )

    @staticmethod
    def _compose_trend_clarification_response(intent: MarketScoutIntent, reason: str) -> MarketScoutResponse:
        return MarketScoutResponse(
            agent="market_scout",
            intent=intent,
            answer="Vui long cung cap job category hoac job family va dia diem de truy van Trend Tracker.",
            confidence="low",
            data={},
            sources=[],
            limitations=[reason],
        )

    @staticmethod
    def _compose_unsupported_response(intent: MarketScoutIntent) -> MarketScoutResponse:
        return MarketScoutResponse(
            agent="market_scout",
            intent=intent,
            answer=(
                "This Market Scout intent is not implemented yet. "
                "Salary benchmark is available; trend and hybrid flows will be added later."
            ),
            confidence="low",
            data={},
            sources=[],
            limitations=["Only salary_benchmark is connected to the agent in the current implementation."],
        )

    @staticmethod
    def _compose_clarification_response() -> MarketScoutResponse:
        return MarketScoutResponse(
            agent="market_scout",
            intent=MarketScoutIntent.UNCLEAR,
            answer="Please ask a salary benchmark question with a job title, location, and experience level.",
            confidence="low",
            data={},
            sources=[],
            limitations=["The current agent can only answer salary benchmark questions."],
        )


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _classify_intent(query: str) -> MarketScoutIntent:
    normalized = query.casefold()
    has_salary_signal = any(keyword in normalized for keyword in _SALARY_KEYWORDS)

    if has_salary_signal:
        return MarketScoutIntent.SALARY_BENCHMARK
    has_trend_signal = any(keyword in normalized for keyword in _TREND_KEYWORDS)
    if has_trend_signal:
        return MarketScoutIntent.TREND_TRACKER
    return MarketScoutIntent.UNCLEAR


def _trend_intent_or_default(value: Any, market_intent: MarketScoutIntent) -> TrendQueryIntent:
    if value is not None:
        try:
            return TrendQueryIntent(str(value))
        except ValueError:
            pass
    if market_intent is MarketScoutIntent.INDUSTRY_DECLINE_RISK:
        return TrendQueryIntent.AUTOMATION_EXPOSURE
    if market_intent is MarketScoutIntent.JOB_DEMAND_FORECAST:
        return TrendQueryIntent.EXTERNAL_OUTLOOK
    return TrendQueryIntent.CURRENT_DEMAND


def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


_TREND_ENTITY_FIELDS = {
    "trend_intent",
    "job_family_id",
    "job_category_id",
    "job_category",
    "location_id",
    "location",
}

def _salary_limitations(result: SalaryBenchmarkFlowResult) -> list[str]:
    benchmark = result.benchmark
    limitations: list[str] = []
    if result.retrieved_records == 0:
        limitations.append("No vector-search records were retrieved for the query.")
    if benchmark.salary_range is None:
        limitations.append("No reliable salary range could be calculated from retrieved salary records.")
    if benchmark.confidence == "low":
        limitations.append("Low confidence because vector matches were weak or salary evidence was limited.")
    if benchmark.discarded_outliers:
        limitations.append(f"{benchmark.discarded_outliers} outlier salary records were excluded.")
    return limitations


_SALARY_KEYWORDS = (
    "salary",
    "compensation",
    "pay",
    "wage",
    "benchmark",
    "luong",
    "lương",
    "muc luong",
    "mức lương",
    "thu nhap",
    "thu nhập",
)

_TREND_KEYWORDS = (
    "trend",
    "demand",
    "forecast",
    "decline",
    "automation",
    "xu huong",
    "xu hướng",
    "nhu cau",
    "nhu cầu",
    "tuyen nhieu",
    "tuyển nhiều",
)
