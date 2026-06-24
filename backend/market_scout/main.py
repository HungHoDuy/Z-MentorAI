from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from backend.market_scout.agent import MarketScoutAgent
from backend.market_scout.schemas import MarketScoutIntent, MarketScoutRequest
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQueryIntent


logger = logging.getLogger(__name__)
app = FastAPI(title="Market Scout", version="1.0.0")


class ScoutRequestBody(BaseModel):
    """Generic Market Scout request for an upstream orchestrator."""

    user_query: str = Field(min_length=1)
    intent_hint: MarketScoutIntent | None = None
    user_context: dict[str, Any] = Field(default_factory=dict)
    entities_hint: dict[str, Any] | None = None


class SalaryBenchmarkRequest(BaseModel):
    user_query: str = Field(min_length=1)


class TrendTrackerRequest(BaseModel):
    trend_intent: TrendQueryIntent = TrendQueryIntent.CURRENT_DEMAND
    job_family_id: str | None = None
    job_category_id: str | None = None
    job_category: str | None = None
    location_id: str | None = None
    location: str | None = None
    user_query: str | None = None


class ScoutResponseBody(BaseModel):
    agent: str
    intent: str
    answer: str
    confidence: str
    data: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


@lru_cache(maxsize=1)
def get_market_scout_agent() -> MarketScoutAgent:
    """Create the agent lazily so health checks do not initialize cloud clients."""

    return MarketScoutAgent()


@app.post("/scout", response_model=ScoutResponseBody)
async def scout_market(
    body: ScoutRequestBody,
    agent: MarketScoutAgent = Depends(get_market_scout_agent),
) -> ScoutResponseBody:
    return await _run_agent(
        agent,
        MarketScoutRequest(
            user_query=body.user_query,
            intent_hint=body.intent_hint,
            user_context=body.user_context,
            entities_hint=body.entities_hint,
        ),
    )


@app.post("/salary-benchmark", response_model=ScoutResponseBody)
async def salary_benchmark(
    body: SalaryBenchmarkRequest,
    agent: MarketScoutAgent = Depends(get_market_scout_agent),
) -> ScoutResponseBody:
    return await _run_agent(
        agent,
        MarketScoutRequest(
            user_query=body.user_query,
            intent_hint=MarketScoutIntent.SALARY_BENCHMARK,
        ),
    )


@app.post("/trend-tracker", response_model=ScoutResponseBody)
async def trend_tracker(
    body: TrendTrackerRequest,
    agent: MarketScoutAgent = Depends(get_market_scout_agent),
) -> ScoutResponseBody:
    entities = {
        "trend_intent": body.trend_intent.value,
        "job_family_id": body.job_family_id,
        "job_category_id": body.job_category_id,
        "job_category": body.job_category,
        "location_id": body.location_id,
        "location": body.location,
    }
    return await _run_agent(
        agent,
        MarketScoutRequest(
            user_query=body.user_query or "Structured Trend Tracker request.",
            intent_hint=_market_intent(body.trend_intent),
            entities_hint={key: value for key, value in entities.items() if value is not None},
        ),
    )


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "market_scout"}


async def _run_agent(agent: MarketScoutAgent, request: MarketScoutRequest) -> ScoutResponseBody:
    try:
        response = await agent.run(request)
    except RuntimeError as exc:
        logger.exception("Market Scout dependency failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Market Scout dependencies are unavailable.",
        ) from exc
    return ScoutResponseBody(**response.to_dict())


def _market_intent(trend_intent: TrendQueryIntent) -> MarketScoutIntent:
    if trend_intent is TrendQueryIntent.AUTOMATION_EXPOSURE:
        return MarketScoutIntent.INDUSTRY_DECLINE_RISK
    if trend_intent is TrendQueryIntent.EXTERNAL_OUTLOOK:
        return MarketScoutIntent.JOB_DEMAND_FORECAST
    return MarketScoutIntent.TREND_TRACKER