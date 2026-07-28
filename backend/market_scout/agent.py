from __future__ import annotations

import inspect
import json
import logging
import re
from time import perf_counter
from typing import Any
import unicodedata

from backend.market_scout.flows.salary_benchmark_flow import SalaryBenchmarkFlow, SalaryBenchmarkFlowResult
from backend.market_scout.flows.trend_tracker_flow import TrendTrackerFlow, TrendTrackerFlowResult
from backend.market_scout.schemas import MarketScoutIntent, MarketScoutRequest, MarketScoutResponse
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQueryInput, TrendQueryIntent
from backend.market_scout.services.market_scout_query_understanding_service import MarketScoutQueryUnderstandingService
from backend.market_scout.services.trend_tracker.trend_entity_extractor_service import TrendEntityExtractorService
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
        trend_entity_extractor: TrendEntityExtractorService | None = None,
        query_understanding_service: Any | None = None,
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
        self.trend_entity_extractor = trend_entity_extractor or TrendEntityExtractorService()
        self.query_understanding_service = query_understanding_service or MarketScoutQueryUnderstandingService()
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
            salary_query = _salary_query_with_context(request)
            flow_start = perf_counter()
            result = salary_flow.run(
                salary_query,
                top_k=self.default_top_k,
                fetch_k=self.default_fetch_k,
            )
            _log_event(
                "market_scout_step",
                agent="market_scout",
                sub_agent="salary_benchmark",
                step="salary_flow_total",
                duration_ms=_duration_ms(flow_start),
                user_query=_short_query(salary_query),
            )
            response = self._compose_salary_response(result)
            _log_event(
                "market_scout_request_end",
                agent="market_scout",
                sub_agent="salary_benchmark",
                confidence=response.confidence,
                duration_ms=_duration_ms(request_start),
                user_query=_short_query(salary_query),
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
            flow_result = _run_trend_flow(trend_flow, trend_input, request.user_query)
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
            intent=_trend_intent_or_default(
                entities.get("trend_intent") or _trend_intent_from_query(request.user_query),
                market_intent,
            ),
            job_family_id=_text_or_none(entities.get("job_family_id") or entities.get("resolved_job_family_id")),
            job_category_id=_text_or_none(entities.get("job_category_id") or entities.get("resolved_job_category_id")),
            job_category=_text_or_none(entities.get("job_category")),
            location_id=_text_or_none(entities.get("location_id")),
            location=_text_or_none(entities.get("location")),
            role_mention=_text_or_none(entities.get("role_mention") or entities.get("target_role")),
            job_sources=_job_sources_or_empty(entities.get("job_sources")),
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
        entities.update(self._trend_entities_from_query_understanding(request.user_query, entities))
        entities.update(self.trend_entity_extractor.extract(request.user_query, entities))
        if self.entity_extractor is not None:
            try:
                extracted = self.entity_extractor.extract(request.user_query, request.user_context)
            except TypeError:
                extracted = self.entity_extractor.extract(request.user_query)
            extracted = await _maybe_await(extracted)
            if isinstance(extracted, dict):
                entities.update({key: value for key, value in extracted.items() if value is not None})
        return entities

    def _trend_entities_from_query_understanding(
        self,
        user_query: str,
        existing_entities: dict[str, Any],
    ) -> dict[str, Any]:
        if self.query_understanding_service is None:
            return {}
        try:
            understanding = self.query_understanding_service.understand(user_query)
        except Exception as exc:
            _log_event(
                "market_scout_query_understanding_failed",
                agent="market_scout",
                user_query=_short_query(user_query),
                error=str(exc),
            )
            return {}
        trend_query = getattr(understanding, "trend_query", None)
        if trend_query is None:
            return {}
        extracted = {
            "trend_intent": getattr(getattr(trend_query, "intent", None), "value", None),
            "role_mention": getattr(trend_query, "role_mention", None),
            "location_text": getattr(trend_query, "location_text", None),
            "job_category_hint": getattr(trend_query, "job_category_hint", None),
            "job_family_hint": getattr(trend_query, "job_family_hint", None),
        }
        extracted.update(_external_outlook_scope_defaults(user_query, extracted))
        return {
            key: value
            for key, value in extracted.items()
            if value is not None and not existing_entities.get(key)
        }

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
            answer=(
                "Minh can ten vi tri/cong viec va khu vuc ban muon xem nhu cau tuyen dung. "
                "Vi du: AI Engineer tai Ha Noi co dang tuyen nhieu khong?"
            ),
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


def _run_trend_flow(trend_flow: Any, trend_input: TrendQueryInput, user_query: str) -> Any:
    if "user_query" in inspect.signature(trend_flow.run).parameters:
        return trend_flow.run(trend_input, user_query=user_query)
    return trend_flow.run(trend_input)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _classify_intent(query: str) -> MarketScoutIntent:
    normalized = _query_key(query)
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
        return TrendQueryIntent.EXTERNAL_OUTLOOK
    if market_intent is MarketScoutIntent.JOB_DEMAND_FORECAST:
        return TrendQueryIntent.EXTERNAL_OUTLOOK
    return TrendQueryIntent.CURRENT_DEMAND


def _trend_intent_from_query(query: str) -> str | None:
    normalized = _query_key(query)
    if any(keyword in normalized for keyword in ("nganh nao", "nghe nao", "cong viec nao", "job nao")):
        return TrendQueryIntent.EXTERNAL_OUTLOOK.value
    if any(
        keyword in normalized
        for keyword in (
            "2026",
            "2027",
            "tuong lai",
            "du bao",
            "forecast",
            "outlook",
            "trien vong",
            "xu huong",
            "phat trien",
            "vai nam toi",
            "con phat trien",
        )
    ):
        return TrendQueryIntent.EXTERNAL_OUTLOOK.value
    if any(keyword in normalized for keyword in ("skill", "ky nang", "yeu cau")):
        return TrendQueryIntent.CURRENT_SKILL_DEMAND.value
    return None


def _query_key(value: Any) -> str:
    text = str(value).replace(chr(273), "d").replace(chr(272), "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    return text.casefold()


def _external_outlook_scope_defaults(user_query: str, entities: dict[str, Any]) -> dict[str, Any]:
    if entities.get("trend_intent") != TrendQueryIntent.EXTERNAL_OUTLOOK.value:
        return {}
    normalized = _query_key(user_query)
    defaults: dict[str, Any] = {}
    if not entities.get("job_family_id") and not entities.get("resolved_job_family_id"):
        if any(keyword in normalized for keyword in ("it", "cntt", "cong nghe", "phan mem", "software", "ai", "data")):
            defaults["job_family_id"] = "digital_telecom"
        elif any(keyword in normalized for keyword in ("sale", "sales", "kinh doanh", "ban hang", "marketing", "ecommerce", "thuong mai")):
            defaults["job_family_id"] = "commercial"
    if not entities.get("location_id") and not entities.get("location") and not entities.get("location_text"):
        defaults["location_id"] = "vietnam"
    return defaults


def _job_sources_or_empty(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]

def _text_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


_TREND_ENTITY_FIELDS = {
    "trend_intent",
    "role_mention",
    "job_family_id",
    "resolved_job_family_id",
    "job_family_hint",
    "job_category_id",
    "resolved_job_category_id",
    "job_category",
    "job_category_hint",
    "location_id",
    "location",
    "location_text",
    "job_sources",
}


def _salary_query_with_context(request: MarketScoutRequest) -> str:
    context = _salary_context_candidates(request)
    job_title = _first_context_text(
        context,
        (
            "job_title",
            "target_role",
            "role",
            "current_role",
            "target_role_hint",
            "career_goal",
        ),
    )
    location = _first_context_text(
        context,
        (
            "location",
            "location_text",
            "preferred_location",
            "location_name",
        ),
    )
    experience_years = _experience_years_from_context(context)

    additions: list[str] = []
    if job_title and job_title.casefold() not in request.user_query.casefold():
        additions.append(f"vi tri {job_title}")
    if location and location.casefold() not in request.user_query.casefold():
        additions.append(f"tai {location}")
    if experience_years is not None and not _query_mentions_experience(request.user_query):
        additions.append(f"voi {experience_years} nam kinh nghiem")

    if not additions:
        return request.user_query
    return f"{request.user_query.strip()} ({'; '.join(additions)})."


def _salary_context_candidates(request: MarketScoutRequest) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for value in (request.entities_hint, request.user_context):
        if isinstance(value, dict):
            candidates.append(value)
            for key in (
                "salary",
                "profile",
                "profile_analysis",
                "structured_profile",
                "cv_profile",
                "cv_context",
            ):
                nested = value.get(key)
                if isinstance(nested, dict):
                    candidates.append(nested)
    for candidate in list(candidates):
        structured = candidate.get("structured_profile")
        if isinstance(structured, dict):
            candidates.append(structured)
    return candidates


def _first_context_text(contexts: list[dict[str, Any]], keys: tuple[str, ...]) -> str | None:
    for context in contexts:
        for key in keys:
            value = context.get(key)
            if isinstance(value, str):
                text = " ".join(value.split())
                if text:
                    return text
    return None


def _experience_years_from_context(contexts: list[dict[str, Any]]) -> int | None:
    for context in contexts:
        for key in (
            "experience_years",
            "years_of_experience",
            "total_experience_years",
            "min_experience",
        ):
            value = _int_or_none(context.get(key))
            if value is not None:
                return value

    seniority = _first_context_text(contexts, ("seniority", "level", "career_level"))
    mapped = _experience_years_from_seniority(seniority)
    if mapped is not None:
        return mapped

    for context in contexts:
        for key in ("experience", "experience_level"):
            text = _first_number_text(context.get(key))
            if text is not None:
                return text
    return None


def _experience_years_from_seniority(value: str | None) -> int | None:
    if not value:
        return None
    normalized = _query_key(value)
    if any(keyword in normalized for keyword in ("intern", "thuc tap", "fresher", "entry")):
        return 1
    if any(keyword in normalized for keyword in ("junior", "jr")):
        return 2
    if any(keyword in normalized for keyword in ("middle", "mid", "intermediate")):
        return 4
    if any(keyword in normalized for keyword in ("senior", "sr")):
        return 6
    if any(keyword in normalized for keyword in ("lead", "principal", "manager")):
        return 8
    return None


def _query_mentions_experience(query: str) -> bool:
    normalized = _query_key(query)
    return bool(re.search(r"\b\d{1,2}\s*(nam|year|years|yr|yrs)\b", normalized)) or "kinh nghiem" in normalized


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _first_number_text(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value)
    match = re.search(r"\d{1,2}", text)
    if not match:
        return None
    return int(match.group(0))

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
    "muc luong",
    "thu nhap",
)

_TREND_KEYWORDS = (
    "trend",
    "demand",
    "forecast",
    "decline",
    "automation",
    "skill",
    "ky nang",
    "yeu cau",
    "xu huong",
    "nhu cau",
    "tuyen nhieu",
    "tuyen dung",
    "dang tuyen",
    "viec lam",
    "co tuyen dung",
    "co dang tuyen",
    "2026",
    "2027",
    "tuong lai",
    "du bao",
    "outlook",
    "trien vong",
    "xu huong",
    "phat trien",
    "vai nam toi",
    "con phat trien",
)




