from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.market_scout.repositories.automation_risk_repository import AutomationRiskRepository
from backend.market_scout.repositories.trend_evidence_repository import TrendEvidenceRepository
from backend.market_scout.repositories.trend_job_fact_repository import TrendJobFactRepository
from backend.market_scout.repositories.trend_snapshot_repository import TrendSnapshotRepository
from backend.market_scout.schemas.hybrid_signal import HybridSignalResult
from backend.market_scout.schemas.trend_query import TrendQuery, TrendQueryInput
from backend.market_scout.services.automation_exposure_service import AutomationExposureService
from backend.market_scout.services.current_demand_service import CurrentDemandService
from backend.market_scout.services.hybrid_signal_service import HybridSignalService
from backend.market_scout.services.skill_frequency_service import SkillFrequencyService
from backend.market_scout.services.trend_query_normalizer import TrendQueryNormalizer


@dataclass(frozen=True)
class TrendTrackerFlowResult:
    """Structured deterministic output consumed by the response-summary layer."""

    query: TrendQuery
    signal: HybridSignalResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": {
                "intent": self.query.intent.value,
                "job_family_id": self.query.job_family_id,
                "job_category_id": self.query.job_category_id,
                "location_id": self.query.location_id,
            },
            "signal": self.signal.to_dict(),
        }


class TrendTrackerFlow:
    """Normalize one Trend Tracker request and produce deterministic evidence."""

    def __init__(
        self,
        *,
        query_normalizer: TrendQueryNormalizer | None = None,
        hybrid_signal_service: HybridSignalService | None = None,
    ) -> None:
        self.query_normalizer = query_normalizer or TrendQueryNormalizer()
        self.hybrid_signal_service = hybrid_signal_service or _build_hybrid_signal_service()

    def run(
        self,
        query_input: TrendQueryInput,
        *,
        as_of_date: date | None = None,
        external_published_after: date | None = None,
    ) -> TrendTrackerFlowResult:
        query = self.query_normalizer.normalize(query_input)
        signal = self.hybrid_signal_service.evaluate(
            query,
            as_of_date=as_of_date,
            external_published_after=external_published_after,
        )
        return TrendTrackerFlowResult(query=query, signal=signal)


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
