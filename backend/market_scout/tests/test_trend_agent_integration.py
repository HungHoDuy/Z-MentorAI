import asyncio

from backend.market_scout.agent import MarketScoutAgent
from backend.market_scout.flows.trend_tracker_flow import TrendTrackerFlowResult
from backend.market_scout.schemas import MarketScoutIntent, MarketScoutRequest
from backend.market_scout.schemas.trend_tracker.hybrid_signal import HybridSignalResult
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery, TrendQueryInput, TrendQueryIntent
from backend.market_scout.services.trend_tracker.trend_summary_service import TrendSummaryService


class FakeTrendFlow:
    def __init__(self, result: TrendTrackerFlowResult) -> None:
        self.result = result
        self.inputs: list[TrendQueryInput] = []

    def run(self, query_input: TrendQueryInput) -> TrendTrackerFlowResult:
        self.inputs.append(query_input)
        return self.result

class FakeTrendSummaryService:
    def summarize(self, result: TrendTrackerFlowResult):
        return TrendSummaryService().summarize(result)

def test_agent_routes_structured_trend_request_through_flow_and_summary() -> None:
    trend_flow = FakeTrendFlow(_trend_result())
    agent = MarketScoutAgent(trend_flow=trend_flow, response_composer=FakeTrendSummaryService())
    request = MarketScoutRequest(
        user_query="Nhu cau tuyen dung phan mem tai Ha Noi ra sao?",
        intent_hint=MarketScoutIntent.TREND_TRACKER,
        entities_hint={
            "trend_intent": "current_demand",
            "job_category_id": "software_it",
            "location_id": "ha-noi",
        },
    )

    response = asyncio.run(agent.run(request))

    assert trend_flow.inputs == [
        TrendQueryInput(
            intent=TrendQueryIntent.CURRENT_DEMAND,
            job_category_id="software_it",
            location_id="ha-noi",
        )
    ]
    assert response.intent == MarketScoutIntent.TREND_TRACKER
    assert response.confidence == "medium"
    assert "28 JD active" in response.answer
    assert response.data["query"]["job_category_id"] == "software_it"
    assert response.sources[0]["url"] == "https://example.com/report"


def test_agent_maps_decline_risk_to_automation_exposure_by_default() -> None:
    trend_flow = FakeTrendFlow(_trend_result())
    agent = MarketScoutAgent(trend_flow=trend_flow, response_composer=FakeTrendSummaryService())

    asyncio.run(
        agent.run(
            MarketScoutRequest(
                user_query="AI co anh huong gi den lap trinh vien?",
                intent_hint=MarketScoutIntent.INDUSTRY_DECLINE_RISK,
                entities_hint={"job_category_id": "software_it", "location_id": "ha-noi"},
            )
        )
    )

    assert trend_flow.inputs[0].intent == TrendQueryIntent.AUTOMATION_EXPOSURE




def test_agent_maps_legacy_market_scout_industry_to_trend_category_and_location() -> None:
    trend_flow = FakeTrendFlow(_trend_result())
    agent = MarketScoutAgent(trend_flow=trend_flow, response_composer=FakeTrendSummaryService())

    asyncio.run(
        agent.run(
            MarketScoutRequest(
                user_query="nhu cau tuyen dung nganh banking tai Ha Noi co cao khong?",
                intent_hint=MarketScoutIntent.TREND_TRACKER,
                entities_hint={"industry": "banking"},
            )
        )
    )

    assert trend_flow.inputs[0] == TrendQueryInput(
        intent=TrendQueryIntent.CURRENT_DEMAND,
        job_category_id="banking",
        location_id="ha-noi",
    )


def test_agent_maps_legacy_target_role_to_trend_category_and_location() -> None:
    trend_flow = FakeTrendFlow(_trend_result())
    agent = MarketScoutAgent(trend_flow=trend_flow, response_composer=FakeTrendSummaryService())

    asyncio.run(
        agent.run(
            MarketScoutRequest(
                user_query="backend engineer tai Ha Noi co dang tuyen dung nhieu khong?",
                intent_hint=MarketScoutIntent.TREND_TRACKER,
                entities_hint={"target_role": "backend engineer"},
            )
        )
    )

    assert trend_flow.inputs[0] == TrendQueryInput(
        intent=TrendQueryIntent.CURRENT_DEMAND,
        job_category_id="software_it",
        location_id="ha-noi",
    )


def test_agent_extracts_job_family_and_location_from_user_query() -> None:
    trend_flow = FakeTrendFlow(_trend_result())
    agent = MarketScoutAgent(trend_flow=trend_flow, response_composer=FakeTrendSummaryService())

    asyncio.run(
        agent.run(
            MarketScoutRequest(
                user_query="nhu cau tuyen dung vi tri nhan vien commercial tai Ha Noi co cao khong?",
                intent_hint=MarketScoutIntent.TREND_TRACKER,
            )
        )
    )

    assert trend_flow.inputs[0] == TrendQueryInput(
        intent=TrendQueryIntent.CURRENT_DEMAND,
        job_family_id="commercial",
        location_id="ha-noi",
    )


def test_agent_extracts_job_category_and_location_from_user_query() -> None:
    trend_flow = FakeTrendFlow(_trend_result())
    agent = MarketScoutAgent(trend_flow=trend_flow, response_composer=FakeTrendSummaryService())

    asyncio.run(
        agent.run(
            MarketScoutRequest(
                user_query="nhu cau tuyen dung nganh banking tai Ha Noi co cao khong?",
                intent_hint=MarketScoutIntent.TREND_TRACKER,
            )
        )
    )

    assert trend_flow.inputs[0] == TrendQueryInput(
        intent=TrendQueryIntent.CURRENT_DEMAND,
        job_category_id="banking",
        location_id="ha-noi",
    )
def _trend_result() -> TrendTrackerFlowResult:
    query = TrendQuery(
        intent=TrendQueryIntent.CURRENT_DEMAND,
        job_family_id="digital_telecom",
        job_category_id="software_it",
        location_id="ha-noi",
    )
    return TrendTrackerFlowResult(
        query=query,
        signal=HybridSignalResult(
            intent=query.intent.value,
            signal="current_demand_high",
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id="2026-W25__digital_telecom__ha-noi",
            period="2026-W25",
            confidence="medium",
            directional_trend=False,
            data={"active_job_count": 28, "distinct_company_count": 19},
            sources=[{"url": "https://example.com/report"}],
            limitations=["One snapshot is not a trend."],
        ),
    )

