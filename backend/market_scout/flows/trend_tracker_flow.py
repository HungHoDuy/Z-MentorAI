from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import json
import logging
from time import perf_counter
from typing import Any

from backend.market_scout.repositories.trend_tracker.automation_risk_repository import AutomationRiskRepository
from backend.market_scout.repositories.trend_tracker.trend_evidence_repository import TrendEvidenceRepository
from backend.market_scout.repositories.trend_tracker.trend_job_fact_repository import TrendJobFactRepository
from backend.market_scout.repositories.trend_tracker.trend_snapshot_repository import TrendSnapshotRepository
from backend.market_scout.schemas.trend_tracker.hybrid_signal import HybridSignalResult
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery, TrendQueryInput, TrendQueryIntent
from backend.market_scout.services.trend_tracker.automation_exposure_service import AutomationExposureService
from backend.market_scout.services.trend_tracker.current_demand_service import CurrentDemandService
from backend.market_scout.services.trend_tracker.hybrid_signal_service import HybridSignalService
from backend.market_scout.services.trend_tracker.role_fact_search_service import RoleFactSearchService
from backend.market_scout.services.trend_tracker.semantic_role_fact_searcher import SemanticRoleFactSearcher
from backend.market_scout.services.trend_tracker.skill_frequency_service import SkillFrequencyService
from backend.market_scout.services.trend_tracker.trend_query_normalizer import TrendQueryNormalizer

logger = logging.getLogger("market_scout")


def _log_step(step: str, query_input: TrendQueryInput, start: float, **fields: Any) -> None:
    logger.info(
        json.dumps(
            {
                "event": "market_scout_step",
                "agent": "market_scout",
                "sub_agent": getattr(query_input.intent, "value", str(query_input.intent)),
                "step": step,
                "duration_ms": round((perf_counter() - start) * 1000, 2),
                "job_family_id": query_input.job_family_id,
                "job_category_id": query_input.job_category_id,
                "location_id": query_input.location_id,
                **fields,
            },
            ensure_ascii=False,
            default=str,
        )
    )

@dataclass(frozen=True)
class TrendTrackerFlowResult:
    """Structured deterministic output consumed by the response-summary layer."""

    query: TrendQuery
    signal: HybridSignalResult
    job_sources: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": {
                "intent": self.query.intent.value,
                "job_family_id": self.query.job_family_id,
                "job_category_id": self.query.job_category_id,
                "location_id": self.query.location_id,
            },
            "job_sources": [dict(source) for source in self.job_sources],
            "signal": self.signal.to_dict(),
        }


class TrendTrackerFlow:
    """Normalize one Trend Tracker request and produce deterministic evidence."""

    def __init__(
        self,
        *,
        query_normalizer: TrendQueryNormalizer | None = None,
        hybrid_signal_service: HybridSignalService | None = None,
        fact_repository: TrendJobFactRepository | None = None,
        role_search_service: RoleFactSearchService | None = None,
        current_demand_service: CurrentDemandService | None = None,
    ) -> None:
        self.query_normalizer = query_normalizer or TrendQueryNormalizer()
        self.hybrid_signal_service = hybrid_signal_service or _build_hybrid_signal_service()
        self.fact_repository = fact_repository
        self.role_search_service = role_search_service
        self.current_demand_service = current_demand_service or CurrentDemandService()
        self.enable_job_source_fallback = fact_repository is not None or hybrid_signal_service is None

    def run(
        self,
        query_input: TrendQueryInput,
        *,
        as_of_date: date | None = None,
        external_published_after: date | None = None,
    ) -> TrendTrackerFlowResult:
        normalize_start = perf_counter()
        query = self.query_normalizer.normalize(query_input)
        _log_step(
            "trend_normalize_query",
            query_input,
            normalize_start,
            normalized_job_family_id=query.job_family_id,
            normalized_job_category_id=query.job_category_id,
            normalized_location_id=query.location_id,
        )

        evaluate_start = perf_counter()
        if query.intent is TrendQueryIntent.CURRENT_DEMAND and query.role_mention:
            signal = self._evaluate_role_current_demand(query)
            step_name = "trend_role_current_demand_evaluate"
        else:
            signal = self.hybrid_signal_service.evaluate(
                query,
                as_of_date=as_of_date,
                external_published_after=external_published_after,
            )
            step_name = "trend_hybrid_signal_evaluate"
        _log_step(
            step_name,
            query_input,
            evaluate_start,
            signal=signal.signal,
            confidence=signal.confidence,
            role_mention=query.role_mention,
        )
        job_sources = list(query.job_sources) or _job_sources_from_signal(signal) or self._fallback_job_sources(query)
        return TrendTrackerFlowResult(query=query, signal=signal, job_sources=job_sources)

    def _evaluate_role_current_demand(self, query: TrendQuery) -> HybridSignalResult:
        role_search_service = self.role_search_service or RoleFactSearchService(
            semantic_searcher=SemanticRoleFactSearcher(),
        )
        matches = role_search_service.search_for_demand(
            role_query=query.role_mention or "",
            location_id=query.location_id,
        )
        demand = self.current_demand_service.evaluate_role_demand(
            matches,
            role_mention=query.role_mention,
            location_id=query.location_id,
        )
        return HybridSignalResult(
            intent=query.intent.value,
            signal=demand.signal,
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id=None,
            period=demand.period,
            confidence=demand.confidence,
            directional_trend=False,
            data=demand.to_dict(),
            sources=list(demand.source_jobs),
            limitations=list(demand.limitations),
        )

    def _fallback_job_sources(self, query: TrendQuery) -> list[dict[str, Any]]:
        if not self.enable_job_source_fallback or not query.job_family_id or not query.location_id:
            return []
        try:
            fact_repository = self.fact_repository or TrendJobFactRepository()
            return fact_repository.list_job_sources(
                job_family_id=query.job_family_id,
                job_category_id=query.job_category_id,
                location_id=query.location_id,
                limit=5,
            )
        except Exception:
            return []


def _job_sources_from_signal(signal: HybridSignalResult) -> list[dict[str, Any]]:
    source_jobs = signal.data.get("source_jobs") if isinstance(signal.data, dict) else None
    if not isinstance(source_jobs, list):
        return []
    return [dict(source) for source in source_jobs if isinstance(source, dict)]

def _build_hybrid_signal_service() -> HybridSignalService:
    snapshot_repository = TrendSnapshotRepository()
    fact_repository = TrendJobFactRepository()
    return HybridSignalService(
        snapshot_repository=snapshot_repository,
        current_demand_service=CurrentDemandService(),
        skill_frequency_service=SkillFrequencyService(fact_repository=fact_repository),
        automation_exposure_service=AutomationExposureService(
            risk_repository=AutomationRiskRepository(),
        ),
        evidence_repository=TrendEvidenceRepository(),
    )
