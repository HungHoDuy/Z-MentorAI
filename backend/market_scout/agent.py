from __future__ import annotations

from backend.market_scout.core.entity_extractor import EntityExtractor
from backend.market_scout.core.intent_classifier import IntentClassifier
from backend.market_scout.core.query_planner import QueryPlanner
from backend.market_scout.core.response_composer import ResponseComposer
from backend.market_scout.flows import HybridFlow, SalaryBenchmarkFlow, TrendTrackerFlow
from backend.market_scout.schemas import MarketScoutIntent, MarketScoutRequest, MarketScoutResponse


class MarketScoutAgent:
    def __init__(
        self,
        intent_classifier: IntentClassifier | None = None,
        entity_extractor: EntityExtractor | None = None,
        query_planner: QueryPlanner | None = None,
        salary_flow: SalaryBenchmarkFlow | None = None,
        trend_flow: TrendTrackerFlow | None = None,
        hybrid_flow: HybridFlow | None = None,
        response_composer: ResponseComposer | None = None,
    ) -> None:
        self.intent_classifier = intent_classifier or IntentClassifier()
        self.entity_extractor = entity_extractor or EntityExtractor()
        self.query_planner = query_planner or QueryPlanner()
        self.salary_flow = salary_flow or SalaryBenchmarkFlow()
        self.trend_flow = trend_flow or TrendTrackerFlow()
        self.hybrid_flow = hybrid_flow or HybridFlow(self.salary_flow, self.trend_flow)
        self.response_composer = response_composer or ResponseComposer()

    async def run(self, request: MarketScoutRequest | str, user_context: dict | None = None) -> MarketScoutResponse:
        if isinstance(request, str):
            request = MarketScoutRequest(user_query=request, user_context=user_context or {})

        intent = await self.intent_classifier.classify(request.user_query)
        entities = request.entities_hint or await self.entity_extractor.extract(request.user_query, request.user_context)
        plan = await self.query_planner.plan(intent, entities)

        if intent == MarketScoutIntent.SALARY_BENCHMARK:
            return await self.salary_flow.run(request.user_query, entities, plan)

        if intent in {
            MarketScoutIntent.TREND_TRACKER,
            MarketScoutIntent.JOB_DEMAND_FORECAST,
            MarketScoutIntent.INDUSTRY_DECLINE_RISK,
        }:
            return await self.trend_flow.run(request.user_query, entities, plan, intent)

        if intent == MarketScoutIntent.MIXED:
            return await self.hybrid_flow.run(request.user_query, entities, plan)

        return self.response_composer.compose_clarification()
