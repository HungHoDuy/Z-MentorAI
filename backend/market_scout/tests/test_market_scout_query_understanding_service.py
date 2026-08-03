import json

from backend.market_scout.schemas import MarketScoutIntent
from backend.market_scout.schemas.salary_benchmark.salary import SalarySearchQuery
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQueryIntent
from backend.market_scout.services.market_scout_query_understanding_service import (
    MarketScoutQueryUnderstandingService,
)


class FakeSalaryQueryUnderstandingService:
    def __init__(self) -> None:
        self.calls = []

    def extract(self, user_query: str) -> SalarySearchQuery:
        self.calls.append(user_query)
        return SalarySearchQuery(
            raw_query=user_query,
            job_title="backend engineer",
            job_title_normalized="backend engineer",
            location="Ha Noi",
            location_normalized="ha noi",
            experience_years=3,
        )


class FakeLlm:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls = []

    def invoke(self, input, **kwargs):
        self.calls.append(input)
        return json.dumps(self.payload, ensure_ascii=False)


def test_understand_salary_uses_existing_salary_normalizer() -> None:
    salary_understanding = FakeSalaryQueryUnderstandingService()
    service = MarketScoutQueryUnderstandingService(
        llm=FakeLlm({"intent": "salary_benchmark", "confidence": "high"}),
        salary_query_understanding_service=salary_understanding,
    )

    result = service.understand("muc luong backend engineer tai Ha Noi voi 3 nam kinh nghiem")

    assert result.intent == MarketScoutIntent.SALARY_BENCHMARK
    assert result.salary_query is not None
    assert result.salary_query.experience_years == 3
    assert result.salary_query.job_title == "backend engineer"
    assert salary_understanding.calls == ["muc luong backend engineer tai Ha Noi voi 3 nam kinh nghiem"]
    assert result.trend_query is None


def test_understand_trend_uses_llm_structured_output() -> None:
    llm = FakeLlm(
        {
            "intent": "trend_tracker",
            "trend_intent": "current_demand",
            "role_mention": "backend engineer",
            "location_text": "Ha Noi",
            "job_category_hint": None,
            "job_family_hint": None,
            "requested_signal": "demand_level",
            "confidence": "high",
        }
    )
    service = MarketScoutQueryUnderstandingService(llm=llm)

    result = service.understand("backend engineer tai Ha Noi co dang tuyen dung nhieu khong?")

    assert result.intent == MarketScoutIntent.TREND_TRACKER
    assert result.trend_query is not None
    assert result.trend_query.intent == TrendQueryIntent.CURRENT_DEMAND
    assert result.trend_query.role_mention == "backend engineer"
    assert result.trend_query.location_text == "Ha Noi"
    assert result.trend_query.confidence == "high"


def test_understand_unclear_can_use_llm_for_intent_when_enabled() -> None:
    llm = FakeLlm(
        {
            "intent": "trend_tracker",
            "trend_intent": "current_skill_demand",
            "role_mention": "business analyst",
            "location_text": "Ho Chi Minh",
            "job_category_hint": None,
            "job_family_hint": None,
            "requested_signal": "skill_frequency",
            "confidence": "medium",
        }
    )
    service = MarketScoutQueryUnderstandingService(llm=llm, use_llm_for_intent=True)

    result = service.understand("business analyst o Ho Chi Minh can ky nang nao?")

    assert result.intent == MarketScoutIntent.TREND_TRACKER
    assert result.trend_query is not None
    assert result.trend_query.intent == TrendQueryIntent.EXTERNAL_OUTLOOK
    assert result.trend_query.role_mention == "business analyst"


def test_understand_ai_replacement_question_as_external_outlook() -> None:
    service = MarketScoutQueryUnderstandingService(
        llm=FakeLlm(
            {
                "intent": "trend_tracker",
                "trend_intent": "external_outlook",
                "role_mention": "ke toan",
                "location_text": None,
                "job_category_hint": None,
                "job_family_hint": None,
                "requested_signal": "external_outlook",
                "confidence": "high",
            }
        )
    )

    result = service.understand("Lieu cong viec ke toan co bi thay the boi AI khong?")

    assert result.intent == MarketScoutIntent.TREND_TRACKER
    assert result.trend_query is not None
    assert result.trend_query.intent == TrendQueryIntent.EXTERNAL_OUTLOOK

def test_understand_upcoming_ai_hiring_question_falls_back_to_external_outlook() -> None:
    service = MarketScoutQueryUnderstandingService(llm=FakeLlm({}))

    result = service.understand("nhu c\u1ea7u tuy\u1ec3n nh\u00e2n l\u1ef1c cho ng\u00e0nh AI s\u1eafp t\u1edbi nh\u01b0 th\u1ebf n\u00e0o?")

    assert result.intent == MarketScoutIntent.TREND_TRACKER
    assert result.trend_query is not None
    assert result.trend_query.intent == TrendQueryIntent.EXTERNAL_OUTLOOK

def test_understand_llm_current_hiring_demand_stays_current_demand() -> None:
    service = MarketScoutQueryUnderstandingService(
        llm=FakeLlm(
            {
                "intent": "trend_tracker",
                "trend_intent": "current_demand",
                "role_mention": "AI Engineer",
                "location_text": "Ha Noi",
                "confidence": "high",
            }
        )
    )

    result = service.understand("AI Engineer tai Ha Noi co dang tuyen nhieu khong?")

    assert result.intent == MarketScoutIntent.TREND_TRACKER
    assert result.trend_query is not None
    assert result.trend_query.intent == TrendQueryIntent.CURRENT_DEMAND


def test_understand_llm_unclear_market_question_defaults_to_external_outlook() -> None:
    service = MarketScoutQueryUnderstandingService(
        llm=FakeLlm(
            {
                "intent": "unclear",
                "confidence": "medium",
            }
        )
    )

    result = service.understand("nganh AI sap toi nhu the nao?")

    assert result.intent == MarketScoutIntent.TREND_TRACKER
    assert result.trend_query is not None
    assert result.trend_query.intent == TrendQueryIntent.EXTERNAL_OUTLOOK

