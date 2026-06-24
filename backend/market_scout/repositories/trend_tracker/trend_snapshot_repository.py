from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

from backend.market_scout.repositories.salary_benchmark.salary_repository import (
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.schemas.trend_tracker.job_family_trend_snapshot import JobFamilyTrendSnapshot
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery
from backend.market_scout.schemas.trend_tracker.trend_snapshot_read import TrendSnapshotReadResult


DEFAULT_TREND_SNAPSHOT_COLLECTION = "trend_snapshots_v2"
MIN_ACTIVE_JOB_COUNT = 10
MIN_DISTINCT_COMPANY_COUNT = 3
FRESH_PERIOD_MAX_AGE_DAYS = 7
AGING_PERIOD_MAX_AGE_DAYS = 14


class TrendSnapshotRepository:
    """Firestore reads for the latest v2 job-family-location snapshot."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        collection_name: str | None = None,
        stream_timeout: int = 30,
    ) -> None:
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.collection_name = collection_name or env_or_default(
            "MARKET_SCOUT_TREND_SNAPSHOT_COLLECTION",
            DEFAULT_TREND_SNAPSHOT_COLLECTION,
        )
        self.stream_timeout = stream_timeout

    def get_latest_for_query(
        self,
        query: TrendQuery,
        *,
        as_of_date: date | None = None,
    ) -> TrendSnapshotReadResult | None:
        return self.get_latest(
            job_family_id=query.job_family_id,
            location_id=query.location_id,
            as_of_date=as_of_date,
        )

    def get_latest(
        self,
        *,
        job_family_id: str,
        location_id: str,
        as_of_date: date | None = None,
    ) -> TrendSnapshotReadResult | None:
        firestore_query = self.firestore_client.collection(self.collection_name)
        firestore_query = _apply_where(firestore_query, "job_family_id", "==", job_family_id)
        firestore_query = _apply_where(firestore_query, "location_id", "==", location_id)
        firestore_query = _apply_order_by_period_desc(firestore_query).limit(1)

        snapshots = list(firestore_query.stream(timeout=self.stream_timeout))
        if not snapshots:
            return None

        snapshot_document = snapshots[0]
        snapshot = job_family_snapshot_from_document(snapshot_document.to_dict() or {})
        if snapshot is None:
            return None

        reference_date = as_of_date or date.today()
        freshness_days = max(0, (reference_date - snapshot.period_end).days)
        return TrendSnapshotReadResult(
            snapshot_id=_optional_text((snapshot_document.to_dict() or {}).get("snapshot_id")) or snapshot_document.id,
            snapshot=snapshot,
            freshness_days=freshness_days,
            freshness_status=_freshness_status(freshness_days),
            sample_status=_sample_status(snapshot),
        )


def job_family_snapshot_from_document(data: Mapping[str, Any]) -> JobFamilyTrendSnapshot | None:
    period = _optional_text(data.get("period"))
    job_family_id = _optional_text(data.get("job_family_id"))
    location_id = _optional_text(data.get("location_id"))
    period_start = _to_date(data.get("period_start"))
    period_end = _to_date(data.get("period_end"))
    if not all((period, job_family_id, location_id, period_start, period_end)):
        return None

    return JobFamilyTrendSnapshot(
        period=period,
        period_start=period_start,
        period_end=period_end,
        job_family_id=job_family_id,
        location_id=location_id,
        observed_job_count=_non_negative_int(data.get("observed_job_count")),
        active_job_count=_non_negative_int(data.get("active_job_count")),
        unknown_active_job_count=_non_negative_int(data.get("unknown_active_job_count")),
        updated_job_count=_non_negative_int(data.get("updated_job_count")),
        distinct_company_count=_non_negative_int(data.get("distinct_company_count")),
        source_job_counts=_int_mapping(data.get("source_job_counts")),
        taxonomy_version=_optional_text(data.get("taxonomy_version")) or "unknown",
    )


def _apply_where(query: Any, field_path: str, operator: str, value: Any) -> Any:
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return query.where(filter=FieldFilter(field_path, operator, value))
    except (ImportError, TypeError):
        return query.where(field_path, operator, value)


def _apply_order_by_period_desc(query: Any) -> Any:
    try:
        return query.order_by("period", direction="DESCENDING")
    except TypeError:
        return query.order_by("period")


def _freshness_status(freshness_days: int) -> str:
    if freshness_days <= FRESH_PERIOD_MAX_AGE_DAYS:
        return "fresh"
    if freshness_days <= AGING_PERIOD_MAX_AGE_DAYS:
        return "aging"
    return "stale"


def _sample_status(snapshot: JobFamilyTrendSnapshot) -> str:
    if (
        snapshot.active_job_count >= MIN_ACTIVE_JOB_COUNT
        and snapshot.distinct_company_count >= MIN_DISTINCT_COMPANY_COUNT
    ):
        return "sufficient"
    return "insufficient_evidence"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


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


def _non_negative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _int_mapping(value: Any) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): _non_negative_int(count)
        for key, count in value.items()
        if _optional_text(key)
    }
