from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping

from backend.market_scout.repositories.salary_repository import (
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.schemas.job_category_trend import JobCategoryTrendJobFact
from backend.market_scout.schemas.job_family_trend_snapshot import JobFamilyTrendSnapshot
from backend.market_scout.services.job_family_trend_snapshot_builder import (
    JobFamilyTrendSnapshotBuilder,
)


DEFAULT_JOB_CATEGORY_TREND_FACT_COLLECTION = "trend_job_facts_v2"
DEFAULT_JOB_FAMILY_TREND_SNAPSHOT_COLLECTION = "trend_snapshots_v2"
DEFAULT_PAGE_SIZE = 500
DEFAULT_BATCH_SIZE = 400
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuildJobFamilyTrendSnapshotsResult:
    status: str
    fact_collection: str
    snapshot_collection: str
    period: str
    period_start: date
    period_end: date
    scanned_documents: int
    parsed_facts: int
    facts_without_job_categories: int
    facts_without_eligible_job_families: int
    skipped_documents: int
    generated_snapshots: int
    written_snapshots: int
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "fact_collection": self.fact_collection,
            "snapshot_collection": self.snapshot_collection,
            "period": self.period,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "scanned_documents": self.scanned_documents,
            "parsed_facts": self.parsed_facts,
            "facts_without_job_categories": self.facts_without_job_categories,
            "facts_without_eligible_job_families": self.facts_without_eligible_job_families,
            "skipped_documents": self.skipped_documents,
            "generated_snapshots": self.generated_snapshots,
            "written_snapshots": self.written_snapshots,
            "dry_run": self.dry_run,
        }


class BuildJobFamilyTrendSnapshotsPipeline:
    """Persist weekly job-family-by-location aggregates from v2 trend facts."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        snapshot_builder: JobFamilyTrendSnapshotBuilder | None = None,
        fact_collection: str | None = None,
        snapshot_collection: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        stream_timeout: int = 60,
        logger: logging.Logger | None = None,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive.")
        if batch_size <= 0 or batch_size > 500:
            raise ValueError("batch_size must be between 1 and 500.")

        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.snapshot_builder = snapshot_builder or JobFamilyTrendSnapshotBuilder()
        self.fact_collection = fact_collection or env_or_default(
            "MARKET_SCOUT_JOB_CATEGORY_TREND_FACT_COLLECTION",
            DEFAULT_JOB_CATEGORY_TREND_FACT_COLLECTION,
        )
        self.snapshot_collection = snapshot_collection or env_or_default(
            "MARKET_SCOUT_JOB_FAMILY_TREND_SNAPSHOT_COLLECTION",
            DEFAULT_JOB_FAMILY_TREND_SNAPSHOT_COLLECTION,
        )
        self.page_size = page_size
        self.batch_size = batch_size
        self.stream_timeout = stream_timeout
        self.logger = logger or LOGGER

    def run(
        self,
        *,
        period_start: date,
        period_end: date,
        period: str | None = None,
        limit: int | None = None,
        dry_run: bool = False,
    ) -> BuildJobFamilyTrendSnapshotsResult:
        self.logger.info(
            "Starting job-family trend snapshots: facts=%s snapshots=%s period_start=%s period_end=%s dry_run=%s",
            self.fact_collection,
            self.snapshot_collection,
            period_start,
            period_end,
            dry_run,
        )

        scanned = 0
        skipped = 0
        without_categories = 0
        without_eligible_families = 0
        facts: list[JobCategoryTrendJobFact] = []
        for snapshot in self._iter_fact_snapshots(limit=limit):
            scanned += 1
            fact = job_category_trend_fact_from_document(snapshot.id, snapshot.to_dict() or {})
            if fact is None:
                skipped += 1
                continue
            if not fact.job_category_ids:
                without_categories += 1
            if not self.snapshot_builder._eligible_job_family_ids(fact):
                without_eligible_families += 1
            facts.append(fact)

        snapshots = self.snapshot_builder.build(
            facts,
            period_start=period_start,
            period_end=period_end,
            period=period,
        )
        label = period or _weekly_period_label(period_end)
        written = self._write_snapshots(snapshots, dry_run=dry_run)

        self.logger.info(
            "Finished job-family trend snapshots: scanned=%s facts=%s without_categories=%s without_eligible_families=%s skipped=%s generated=%s written=%s",
            scanned,
            len(facts),
            without_categories,
            without_eligible_families,
            skipped,
            len(snapshots),
            written,
        )
        return BuildJobFamilyTrendSnapshotsResult(
            status="success",
            fact_collection=self.fact_collection,
            snapshot_collection=self.snapshot_collection,
            period=label,
            period_start=period_start,
            period_end=period_end,
            scanned_documents=scanned,
            parsed_facts=len(facts),
            facts_without_job_categories=without_categories,
            facts_without_eligible_job_families=without_eligible_families,
            skipped_documents=skipped,
            generated_snapshots=len(snapshots),
            written_snapshots=written,
            dry_run=dry_run,
        )

    def _iter_fact_snapshots(self, *, limit: int | None = None):
        collection_ref = self.firestore_client.collection(self.fact_collection)
        last_snapshot = None
        yielded = 0

        while True:
            page_size = self.page_size
            if limit is not None:
                remaining = limit - yielded
                if remaining <= 0:
                    return
                page_size = min(page_size, remaining)

            query = collection_ref.order_by("__name__").limit(page_size)
            if last_snapshot is not None:
                query = query.start_after(last_snapshot)
            page = list(query.stream(timeout=self.stream_timeout))
            if not page:
                return

            for snapshot in page:
                yield snapshot
                yielded += 1
            last_snapshot = page[-1]

    def _write_snapshots(self, snapshots: list[JobFamilyTrendSnapshot], *, dry_run: bool) -> int:
        if dry_run or not snapshots:
            return 0

        collection_ref = self.firestore_client.collection(self.snapshot_collection)
        batch = self.firestore_client.batch()
        pending = 0
        written = 0
        for snapshot in snapshots:
            document_id = job_family_snapshot_document_id(snapshot)
            document = snapshot.to_dict()
            document.update(
                {
                    "snapshot_id": document_id,
                    "fact_collection": self.fact_collection,
                    "schema_version": 2,
                }
            )
            batch.set(collection_ref.document(document_id), document, merge=True)
            pending += 1
            written += 1
            if pending >= self.batch_size:
                batch.commit()
                batch = self.firestore_client.batch()
                pending = 0

        if pending:
            batch.commit()
        return written


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


def job_family_snapshot_document_id(snapshot: JobFamilyTrendSnapshot) -> str:
    return "__".join(
        _document_part(value)
        for value in (snapshot.period, snapshot.job_family_id, snapshot.location_id)
    )


def _document_part(value: str) -> str:
    return value.replace("/", "-").strip() or "unknown"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _optional_text(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


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

    to_datetime = getattr(value, "to_datetime", None)
    if callable(to_datetime):
        parsed = to_datetime()
        if isinstance(parsed, datetime):
            return parsed.date()

    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), pattern).date()
        except ValueError:
            continue
    return None


def _weekly_period_label(period_end: date) -> str:
    iso_year, iso_week, _ = period_end.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"
