from __future__ import annotations

from datetime import date
import re
import unicodedata
from typing import Any, Protocol

from backend.market_scout.repositories.trend_tracker.trend_evidence_repository import TrendEvidenceRepository
from backend.market_scout.repositories.trend_tracker.trend_snapshot_repository import TrendSnapshotRepository
from backend.market_scout.schemas.trend_tracker.hybrid_signal import HybridSignalResult
from backend.market_scout.schemas.trend_tracker.trend_external_evidence import TrendEvidenceMatch
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery, TrendQueryIntent
from backend.market_scout.schemas.trend_tracker.trend_snapshot_read import TrendSnapshotReadResult
from backend.market_scout.services.trend_tracker.current_demand_service import CurrentDemandService
from backend.market_scout.services.trend_tracker.skill_frequency_service import SkillFrequencyService


DEFAULT_MIN_EXTERNAL_RELIABILITY_SCORE = 0.7
DEFAULT_EXTERNAL_EVIDENCE_LIMIT = 5


class ExternalOutlookLiveSearcher(Protocol):
    def search(self, user_query: str, query: TrendQuery) -> list[TrendEvidenceMatch]:
        ...


class HybridSignalService:
    """Orchestrate internal demand, skill, automation, and external-outlook evidence."""

    def __init__(
        self,
        *,
        snapshot_repository: TrendSnapshotRepository,
        current_demand_service: CurrentDemandService,
        skill_frequency_service: SkillFrequencyService,
        evidence_repository: TrendEvidenceRepository,
        live_search_service: ExternalOutlookLiveSearcher | None = None,
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
        self.evidence_repository = evidence_repository
        self.live_search_service = live_search_service
        self.min_external_reliability_score = min_external_reliability_score
        self.external_evidence_limit = external_evidence_limit

    def evaluate(
        self,
        query: TrendQuery,
        *,
        as_of_date: date | None = None,
        external_published_after: date | None = None,
        user_query: str | None = None,
    ) -> HybridSignalResult:
        if query.intent is TrendQueryIntent.EXTERNAL_OUTLOOK:
            return self._external_outlook(query, external_published_after, user_query)

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

    def _external_outlook(
        self,
        query: TrendQuery,
        external_published_after: date | None,
        user_query: str | None,
    ) -> HybridSignalResult:
        evidence = self._external_evidence(query, external_published_after, user_query=user_query)
        if not evidence:
            return HybridSignalResult(
                intent=query.intent.value,
                signal="insufficient_evidence",
                job_family_id=query.job_family_id,
                job_category_id=query.job_category_id,
                location_id=query.location_id,
                snapshot_id=None,
                period=None,
                confidence="low",
                directional_trend=False,
                data={"evidence_count": 0, "claims": []},
                sources=[],
                limitations=["No high-reliability external outlook evidence matches this scope."],
            )
        return HybridSignalResult(
            intent=query.intent.value,
            signal="external_outlook",
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id=None,
            period=_outlook_period(evidence),
            confidence="medium",
            directional_trend=False,
            data={
                "evidence_count": len(evidence),
                "claims": [_evidence_claim(item) for item in evidence],
                "scope_location_ids": _evidence_locations(evidence),
            },
            sources=[_evidence_source(item) for item in evidence],
            limitations=[
                "External evidence is contextual outlook and does not replace internal current-demand data.",
                "This is not a guaranteed forecast; it summarizes cited sources currently available to Z-MentorAI.",
            ],
        )

    def _external_evidence(
        self,
        query: TrendQuery,
        published_after: date | None,
        *,
        user_query: str | None = None,
    ) -> list[TrendEvidenceMatch]:
        if user_query and self.live_search_service is not None:
            try:
                live_evidence = self.live_search_service.search(user_query, query)
            except Exception:
                live_evidence = []
            if live_evidence:
                return live_evidence

        cached_evidence = self.evidence_repository.list_for_external_outlook(
            job_family_id=query.job_family_id,
            location_id=query.location_id,
            published_after=published_after,
            min_reliability_score=self.min_external_reliability_score,
            limit=self.external_evidence_limit,
        )
        return _select_relevant_cached_evidence(cached_evidence, user_query)
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


def _select_relevant_cached_evidence(
    evidence: list[TrendEvidenceMatch],
    user_query: str | None,
) -> list[TrendEvidenceMatch]:
    if not evidence or not user_query:
        return evidence

    query_tokens = _meaningful_tokens(user_query)
    if not query_tokens:
        return evidence

    scored: list[tuple[int, TrendEvidenceMatch]] = []
    for item in evidence:
        evidence_text = " ".join(
            filter(
                None,
                (
                    item.evidence.exact_claim,
                    item.evidence.citation,
                    item.evidence.period,
                    item.source.source_name,
                    item.source.publisher,
                ),
            )
        )
        overlap = len(query_tokens & _meaningful_tokens(evidence_text))
        if overlap > 0:
            scored.append((overlap, item))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [item for _, item in scored]


def _meaningful_tokens(value: str) -> set[str]:
    normalized = _normalize_text(value)
    return {
        token
        for token in normalized.split()
        if len(token) >= 3 and token not in _EXTERNAL_OUTLOOK_STOPWORDS
    }


def _normalize_text(value: str) -> str:
    text = str(value or "").replace(chr(273), "d").replace(chr(272), "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_EXTERNAL_OUTLOOK_STOPWORDS = {
    "nam",
    "nganh",
    "nghe",
    "con",
    "co",
    "khong",
    "trong",
    "thoi",
    "dai",
    "hien",
    "tai",
    "nay",
    "gi",
    "la",
    "va",
    "the",
    "nao",
    "nhung",
    "cac",
    "cho",
    "toi",
    "cua",
    "ve",
    "duoc",
    "kha",
    "nang",
    "phat",
    "trien",
    "2026",
    "2027",
}

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


def _outlook_period(evidence: list[TrendEvidenceMatch]) -> str | None:
    periods = [item.evidence.period for item in evidence if item.evidence.period]
    return ", ".join(dict.fromkeys(periods[:3])) or None


def _evidence_locations(evidence: list[TrendEvidenceMatch]) -> list[str]:
    locations: list[str] = []
    for item in evidence:
        for location_id in item.evidence.location_ids:
            if location_id not in locations:
                locations.append(location_id)
    return locations


def _single_snapshot_limitation() -> str:
    return "Only one internal weekly snapshot is available; this output is not a directional market trend."





