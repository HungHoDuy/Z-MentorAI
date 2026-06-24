from __future__ import annotations

from datetime import date
from typing import Any

from backend.market_scout.repositories.trend_tracker.trend_evidence_repository import TrendEvidenceRepository
from backend.market_scout.repositories.trend_tracker.trend_snapshot_repository import TrendSnapshotRepository
from backend.market_scout.schemas.trend_tracker.hybrid_signal import HybridSignalResult
from backend.market_scout.schemas.trend_tracker.trend_external_evidence import TrendEvidenceMatch
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery, TrendQueryIntent
from backend.market_scout.schemas.trend_tracker.trend_snapshot_read import TrendSnapshotReadResult
from backend.market_scout.services.trend_tracker.automation_exposure_service import AutomationExposureService
from backend.market_scout.services.trend_tracker.current_demand_service import CurrentDemandService
from backend.market_scout.services.trend_tracker.skill_frequency_service import SkillFrequencyService


DEFAULT_MIN_EXTERNAL_RELIABILITY_SCORE = 0.7
DEFAULT_EXTERNAL_EVIDENCE_LIMIT = 5


class HybridSignalService:
    """Orchestrate internal demand, skill, automation, and external-outlook evidence."""

    def __init__(
        self,
        *,
        snapshot_repository: TrendSnapshotRepository,
        current_demand_service: CurrentDemandService,
        skill_frequency_service: SkillFrequencyService,
        automation_exposure_service: AutomationExposureService,
        evidence_repository: TrendEvidenceRepository,
        min_external_reliability_score: float = DEFAULT_MIN_EXTERNAL_RELIABILITY_SCORE,
        external_evidence_limit: int = DEFAULT_EXTERNAL_EVIDENCE_LIMIT,
    ) -> None:
        if not 0 <= min_external_reliability_score <= 1:
            raise ValueError("min_external_reliability_score must be between 0 and 1.")
        if external_evidence_limit <= 0:
            raise ValueError("external_evidence_limit must be positive.")
        self.snapshot_repository = snapshot_repository
        self.current_demand_service = current_demand_service
        self.skill_frequency_service = skill_frequency_service
        self.automation_exposure_service = automation_exposure_service
        self.evidence_repository = evidence_repository
        self.min_external_reliability_score = min_external_reliability_score
        self.external_evidence_limit = external_evidence_limit

    def evaluate(
        self,
        query: TrendQuery,
        *,
        as_of_date: date | None = None,
        external_published_after: date | None = None,
    ) -> HybridSignalResult:
        snapshot_read = self.snapshot_repository.get_latest_for_query(query, as_of_date=as_of_date)
        if snapshot_read is None:
            return self._insufficient(
                query,
                snapshot_read=None,
                reason="No internal job-demand snapshot exists for this job-family and location cohort.",
            )
        if snapshot_read.sample_status != "sufficient":
            return self._insufficient(
                query,
                snapshot_read=snapshot_read,
                reason="The latest internal snapshot does not meet the minimum active-job and company sample thresholds.",
            )

        if query.intent is TrendQueryIntent.CURRENT_DEMAND:
            return self._current_demand(query, snapshot_read, external_published_after)
        if query.intent is TrendQueryIntent.CURRENT_SKILL_DEMAND:
            return self._current_skill_demand(query, snapshot_read)
        if query.intent is TrendQueryIntent.AUTOMATION_EXPOSURE:
            return self._automation_exposure(query, snapshot_read)
        if query.intent is TrendQueryIntent.EXTERNAL_OUTLOOK:
            return self._external_outlook(query, snapshot_read, external_published_after)
        if query.intent is TrendQueryIntent.DEMAND_PRESSURE:
            return self._out_of_scope(query, snapshot_read)
        raise ValueError(f"Unsupported trend query intent: {query.intent}")

    def _current_demand(
        self,
        query: TrendQuery,
        snapshot_read: TrendSnapshotReadResult,
        external_published_after: date | None,
    ) -> HybridSignalResult:
        demand = self.current_demand_service.evaluate(snapshot_read.snapshot)
        evidence = self._external_evidence(query, external_published_after)
        has_external_evidence = bool(evidence)
        return HybridSignalResult(
            intent=query.intent.value,
            signal=demand.signal,
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id=snapshot_read.snapshot_id,
            period=snapshot_read.period,
            confidence="medium" if has_external_evidence else "low",
            directional_trend=False,
            data=demand.to_dict(),
            sources=[_evidence_source(item) for item in evidence],
            limitations=[
                *demand.limitations,
                _single_snapshot_limitation(),
                *([] if has_external_evidence else ["No matching high-reliability external outlook evidence was found."]),
            ],
        )

    def _current_skill_demand(
        self,
        query: TrendQuery,
        snapshot_read: TrendSnapshotReadResult,
    ) -> HybridSignalResult:
        skill_demand = self.skill_frequency_service.evaluate(
            snapshot_read.snapshot,
            job_category_id=query.job_category_id,
        )
        return HybridSignalResult(
            intent=query.intent.value,
            signal=skill_demand.signal,
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id=snapshot_read.snapshot_id,
            period=snapshot_read.period,
            confidence=skill_demand.confidence,
            directional_trend=False,
            data=skill_demand.to_dict(),
            sources=[],
            limitations=[*skill_demand.limitations, _single_snapshot_limitation()],
        )

    def _automation_exposure(
        self,
        query: TrendQuery,
        snapshot_read: TrendSnapshotReadResult,
    ) -> HybridSignalResult:
        if query.job_category_id is None:
            return self._insufficient(
                query,
                snapshot_read=snapshot_read,
                reason="Automation exposure requires a canonical job category, not only a broad job family.",
            )

        exposure = self.automation_exposure_service.evaluate(query.job_category_id)
        source = []
        if exposure.source_url:
            source.append({"url": exposure.source_url, "source_type": "automation_exposure_lookup"})
        return HybridSignalResult(
            intent=query.intent.value,
            signal=exposure.signal,
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id=snapshot_read.snapshot_id,
            period=snapshot_read.period,
            confidence=exposure.confidence,
            directional_trend=False,
            data={
                "exposure_level": exposure.exposure_level,
                "risk_reason": exposure.risk_reason,
                "protected_tasks": list(exposure.protected_tasks),
                "at_risk_tasks": list(exposure.at_risk_tasks),
            },
            sources=source,
            limitations=[*exposure.limitations, _single_snapshot_limitation()],
        )

    def _external_outlook(
        self,
        query: TrendQuery,
        snapshot_read: TrendSnapshotReadResult,
        external_published_after: date | None,
    ) -> HybridSignalResult:
        evidence = self._external_evidence(query, external_published_after)
        if not evidence:
            return self._insufficient(
                query,
                snapshot_read=snapshot_read,
                reason="No high-reliability external outlook evidence matches this job-family and location scope.",
            )
        return HybridSignalResult(
            intent=query.intent.value,
            signal="external_outlook",
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id=snapshot_read.snapshot_id,
            period=snapshot_read.period,
            confidence="medium",
            directional_trend=False,
            data={"evidence_count": len(evidence), "claims": [_evidence_claim(item) for item in evidence]},
            sources=[_evidence_source(item) for item in evidence],
            limitations=[
                "External evidence is contextual outlook and does not replace the internal current-demand snapshot.",
                _single_snapshot_limitation(),
            ],
        )

    def _external_evidence(
        self,
        query: TrendQuery,
        published_after: date | None,
    ) -> list[TrendEvidenceMatch]:
        return self.evidence_repository.list_for_external_outlook(
            job_family_id=query.job_family_id,
            location_id=query.location_id,
            published_after=published_after,
            min_reliability_score=self.min_external_reliability_score,
            limit=self.external_evidence_limit,
        )

    def _insufficient(
        self,
        query: TrendQuery,
        *,
        snapshot_read: TrendSnapshotReadResult | None,
        reason: str,
    ) -> HybridSignalResult:
        snapshot = snapshot_read.snapshot if snapshot_read else None
        return HybridSignalResult(
            intent=query.intent.value,
            signal="insufficient_evidence",
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id=snapshot_read.snapshot_id if snapshot_read else None,
            period=snapshot.period if snapshot else None,
            confidence="low",
            directional_trend=False,
            data={
                "active_job_count": snapshot.active_job_count if snapshot else None,
                "distinct_company_count": snapshot.distinct_company_count if snapshot else None,
            },
            sources=[],
            limitations=[reason, _single_snapshot_limitation()],
        )

    def _out_of_scope(self, query: TrendQuery, snapshot_read: TrendSnapshotReadResult) -> HybridSignalResult:
        return HybridSignalResult(
            intent=query.intent.value,
            signal="out_of_scope",
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id=snapshot_read.snapshot_id,
            period=snapshot_read.period,
            confidence="low",
            directional_trend=False,
            data={},
            sources=[],
            limitations=[
                "Demand pressure cannot be inferred from job listings alone.",
                "It requires supply-side metrics such as applicant volume, time-to-fill, or vacancy duration.",
                _single_snapshot_limitation(),
            ],
        )


def _evidence_source(match: TrendEvidenceMatch) -> dict[str, Any]:
    return {
        "source_id": match.source.source_id,
        "source_name": match.source.source_name,
        "publisher": match.source.publisher,
        "url": match.source.url,
        "published_at": match.source.published_at.isoformat(),
        "reliability_score": match.source.reliability_score,
        "citation": match.evidence.citation,
    }


def _evidence_claim(match: TrendEvidenceMatch) -> dict[str, Any]:
    return {
        "evidence_id": match.evidence.evidence_id,
        "direction": match.evidence.direction,
        "exact_claim": match.evidence.exact_claim,
        "metric_value": match.evidence.metric_value,
        "metric_unit": match.evidence.metric_unit,
        "citation": match.evidence.citation,
        "confidence": match.evidence.confidence,
    }


def _single_snapshot_limitation() -> str:
    return "Only one internal weekly snapshot is available; this output is not a directional market trend."
