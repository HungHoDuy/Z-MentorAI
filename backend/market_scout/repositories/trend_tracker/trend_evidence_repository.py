from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

from backend.market_scout.repositories.salary_benchmark.salary_repository import (
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.schemas.trend_tracker.trend_external_evidence import (
    TrendEvidence,
    TrendEvidenceMatch,
    TrendSource,
)


DEFAULT_TREND_SOURCE_COLLECTION = "trend_sources"
DEFAULT_TREND_EVIDENCE_COLLECTION = "trend_evidence"


class TrendEvidenceRepository:
    """Retrieve cited external outlook claims without replacing internal demand data."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        source_collection: str | None = None,
        evidence_collection: str | None = None,
        stream_timeout: int = 30,
    ) -> None:
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.source_collection = source_collection or env_or_default(
            "MARKET_SCOUT_TREND_SOURCE_COLLECTION", DEFAULT_TREND_SOURCE_COLLECTION
        )
        self.evidence_collection = evidence_collection or env_or_default(
            "MARKET_SCOUT_TREND_EVIDENCE_COLLECTION", DEFAULT_TREND_EVIDENCE_COLLECTION
        )
        self.stream_timeout = stream_timeout

    def list_for_external_outlook(
        self,
        *,
        job_family_id: str,
        location_id: str,
        published_after: date | None = None,
        min_reliability_score: float = 0.7,
        limit: int = 10,
    ) -> list[TrendEvidenceMatch]:
        if not 0 <= min_reliability_score <= 1:
            raise ValueError("min_reliability_score must be between 0 and 1.")
        if limit <= 0:
            raise ValueError("limit must be positive.")

        query = _apply_array_contains(
            self.firestore_client.collection(self.evidence_collection),
            "job_family_ids",
            job_family_id,
        )
        evidence_documents = list(query.stream(timeout=self.stream_timeout))
        source_cache: dict[str, TrendSource | None] = {}
        candidates: list[TrendEvidenceMatch] = []
        for document in evidence_documents:
            evidence = trend_evidence_from_document(document.id, document.to_dict() or {})
            if evidence is None:
                continue
            source = source_cache.get(evidence.source_id)
            if evidence.source_id not in source_cache:
                source = self._get_source(evidence.source_id)
                source_cache[evidence.source_id] = source
            if source is not None:
                candidates.append(TrendEvidenceMatch(source=source, evidence=evidence))

        return select_external_outlook_evidence(
            candidates,
            job_family_id=job_family_id,
            location_id=location_id,
            published_after=published_after,
            min_reliability_score=min_reliability_score,
            limit=limit,
        )

    def _get_source(self, source_id: str) -> TrendSource | None:
        snapshot = self.firestore_client.collection(self.source_collection).document(source_id).get()
        if not getattr(snapshot, "exists", False):
            return None
        return trend_source_from_document(snapshot.id, snapshot.to_dict() or {})


def select_external_outlook_evidence(
    candidates: list[TrendEvidenceMatch],
    *,
    job_family_id: str,
    location_id: str,
    published_after: date | None,
    min_reliability_score: float,
    limit: int,
) -> list[TrendEvidenceMatch]:
    matches = [
        candidate
        for candidate in candidates
        if job_family_id in candidate.evidence.job_family_ids
        and location_id in candidate.evidence.location_ids
        and location_id in candidate.source.scope_location_ids
        and candidate.source.reliability_score >= min_reliability_score
        and (published_after is None or candidate.source.published_at >= published_after)
    ]
    matches.sort(
        key=lambda candidate: (
            candidate.source.published_at,
            candidate.source.reliability_score,
            candidate.evidence.evidence_id,
        ),
        reverse=True,
    )
    return matches[:limit]


def trend_source_from_document(document_id: str, data: Mapping[str, Any]) -> TrendSource | None:
    source_id = _text(data.get("source_id")) or document_id
    source_name = _text(data.get("source_name"))
    publisher = _text(data.get("publisher"))
    source_type = _text(data.get("source_type"))
    published_at = _to_date(data.get("published_at"))
    fetched_at = _to_date(data.get("fetched_at"))
    url = _text(data.get("url"))
    reliability_score = _score(data.get("reliability_score"))
    scope_location_ids = _string_list(data.get("scope_location_ids"))
    if not all((source_id, source_name, publisher, source_type, published_at, fetched_at, url)):
        return None
    if reliability_score is None or not scope_location_ids:
        return None
    return TrendSource(
        source_id=source_id,
        source_name=source_name,
        publisher=publisher,
        source_type=source_type,
        published_at=published_at,
        fetched_at=fetched_at,
        reliability_score=reliability_score,
        scope_location_ids=scope_location_ids,
        scope_period=_text(data.get("scope_period")),
        url=url,
        content_hash=_text(data.get("content_hash")),
        notes=_text(data.get("notes")),
    )


def trend_evidence_from_document(document_id: str, data: Mapping[str, Any]) -> TrendEvidence | None:
    evidence_id = _text(data.get("evidence_id")) or document_id
    source_id = _text(data.get("source_id"))
    direction = _text(data.get("direction"))
    exact_claim = _text(data.get("exact_claim"))
    citation = _text(data.get("citation"))
    confidence = _text(data.get("confidence"))
    job_family_ids = _string_list(data.get("job_family_ids"))
    location_ids = _string_list(data.get("location_ids"))
    if not all((evidence_id, source_id, direction, exact_claim, citation, confidence)):
        return None
    if not job_family_ids or not location_ids:
        return None
    return TrendEvidence(
        evidence_id=evidence_id,
        source_id=source_id,
        job_family_ids=job_family_ids,
        job_category_ids=_string_list(data.get("job_category_ids")),
        location_ids=location_ids,
        period=_text(data.get("period")),
        direction=direction,
        exact_claim=exact_claim,
        metric_value=_number(data.get("metric_value")),
        metric_unit=_text(data.get("metric_unit")),
        citation=citation,
        confidence=confidence,
    )


def _apply_array_contains(query: Any, field_path: str, value: str) -> Any:
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return query.where(filter=FieldFilter(field_path, "array_contains", value))
    except (ImportError, TypeError):
        return query.where(field_path, "array_contains", value)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    result = " ".join(str(value).split())
    return result or None


def _string_list(value: Any) -> list[str]:
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return list(dict.fromkeys(text for item in values if (text := _text(item))))


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), pattern).date()
        except ValueError:
            continue
    return None


def _score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if 0 <= score <= 1 else None


def _number(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
