from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

from backend.market_scout.repositories.salary_benchmark.salary_repository import (
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.schemas.trend_tracker.job_category_trend import JobCategoryTrendJobFact
from backend.market_scout.schemas.trend_tracker.job_family_trend_snapshot import JobFamilyTrendSnapshot


DEFAULT_TREND_FACT_COLLECTION = "trend_job_facts_v2"


class TrendJobFactRepository:
    """Read active v2 job facts for a snapshot's family-location cohort."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        collection_name: str | None = None,
        stream_timeout: int = 60,
    ) -> None:
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.collection_name = collection_name or env_or_default(
            "MARKET_SCOUT_JOB_CATEGORY_TREND_FACT_COLLECTION",
            DEFAULT_TREND_FACT_COLLECTION,
        )
        self.stream_timeout = stream_timeout

    def list_active_for_snapshot(
        self,
        snapshot: JobFamilyTrendSnapshot,
        *,
        job_category_id: str | None = None,
    ) -> list[JobCategoryTrendJobFact]:
        firestore_query = self.firestore_client.collection(self.collection_name)
        firestore_query = _apply_where(
            firestore_query,
            "job_family_ids",
            "array_contains",
            snapshot.job_family_id,
        )

        facts_by_job_key: dict[str, JobCategoryTrendJobFact] = {}
        for document in firestore_query.stream(timeout=self.stream_timeout):
            fact = job_category_trend_fact_from_document(document.id, document.to_dict() or {})
            if fact is None or not _matches_snapshot_cohort(
                fact,
                snapshot=snapshot,
                job_category_id=job_category_id,
            ):
                continue

            current = facts_by_job_key.get(fact.job_key)
            if current is None or _is_newer_fact(fact, current):
                facts_by_job_key[fact.job_key] = fact

        return sorted(facts_by_job_key.values(), key=lambda fact: fact.job_key)


def job_category_trend_fact_from_document(
    document_id: str,
    data: Mapping[str, Any],
) -> JobCategoryTrendJobFact | None:
    job_title = _optional_text(data.get("job_title"))
    if not job_title:
        return None

    return JobCategoryTrendJobFact(
        job_key=_optional_text(data.get("job_key")) or document_id,
        source=_optional_text(data.get("source")) or "unknown",
        source_job_id=_optional_text(data.get("source_job_id")),
        job_url=_optional_text(data.get("job_url")),
        canonical_job_url=_optional_text(data.get("canonical_job_url")),
        job_title=job_title,
        company=_optional_text(data.get("company")),
        company_key=_optional_text(data.get("company_key")),
        location_ids=_string_list(data.get("location_ids")),
        seniority=_optional_text(data.get("seniority")),
        employment_type=_optional_text(data.get("employment_type")),
        source_updated_at=_to_date(data.get("source_updated_at")),
        source_expires_at=_to_date(data.get("source_expires_at")),
        is_active=_optional_bool(data.get("is_active")),
        content_hash=_optional_text(data.get("content_hash")) or "",
        requirements_text=_optional_text(data.get("requirements_text")),
        description_text=_optional_text(data.get("description_text")),
        raw_job_category_labels=_string_list(data.get("raw_job_category_labels")),
        job_category_ids=_string_list(data.get("job_category_ids")),
        job_family_ids=_string_list(data.get("job_family_ids")),
        unmatched_job_category_labels=_string_list(data.get("unmatched_job_category_labels")),
        invalid_job_category_labels=_string_list(data.get("invalid_job_category_labels")),
        taxonomy_version=_optional_text(data.get("taxonomy_version")) or "unknown",
    )


def _matches_snapshot_cohort(
    fact: JobCategoryTrendJobFact,
    *,
    snapshot: JobFamilyTrendSnapshot,
    job_category_id: str | None,
) -> bool:
    if snapshot.location_id not in fact.location_ids:
        return False
    if fact.source_expires_at is None or fact.source_expires_at < snapshot.period_end:
        return False
    if job_category_id and job_category_id not in fact.job_category_ids:
        return False
    return True


def _is_newer_fact(candidate: JobCategoryTrendJobFact, current: JobCategoryTrendJobFact) -> bool:
    candidate_rank = (
        candidate.source_updated_at or date.min,
        candidate.source_expires_at or date.min,
        candidate.content_hash,
    )
    current_rank = (
        current.source_updated_at or date.min,
        current.source_expires_at or date.min,
        current.content_hash,
    )
    return candidate_rank > current_rank


def _apply_where(query: Any, field_path: str, operator: str, value: Any) -> Any:
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return query.where(filter=FieldFilter(field_path, operator, value))
    except (ImportError, TypeError):
        return query.where(field_path, operator, value)


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple, set)) else [value]
    values_by_text: dict[str, str] = {}
    for item in values:
        text = _optional_text(item)
        if text:
            values_by_text.setdefault(text, text)
    return list(values_by_text.values())


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return None


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
