from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from datetime import date

from backend.market_scout.schemas.trend_tracker.job_category_trend import JobCategoryTrendJobFact
from backend.market_scout.schemas.trend_tracker.job_family_trend_snapshot import JobFamilyTrendSnapshot
from backend.market_scout.services.trend_tracker.job_category_taxonomy_service import JobCategoryTaxonomyService


SnapshotKey = tuple[str, str]


class JobFamilyTrendSnapshotBuilder:
    """Aggregate v2 facts by eligible job family and location for one week."""

    def __init__(self, *, taxonomy_service: JobCategoryTaxonomyService | None = None) -> None:
        self.taxonomy_service = taxonomy_service or JobCategoryTaxonomyService()

    def build(
        self,
        facts: Iterable[JobCategoryTrendJobFact],
        *,
        period_start: date,
        period_end: date,
        period: str | None = None,
    ) -> list[JobFamilyTrendSnapshot]:
        if period_start > period_end:
            raise ValueError("period_start must be on or before period_end.")

        grouped_facts: dict[SnapshotKey, dict[str, JobCategoryTrendJobFact]] = {}
        for fact in facts:
            if not _is_observable_by(fact, period_end):
                continue
            for key in self._snapshot_keys(fact):
                facts_by_job_key = grouped_facts.setdefault(key, {})
                existing = facts_by_job_key.get(fact.job_key)
                if existing is None or _is_newer_fact(fact, existing):
                    facts_by_job_key[fact.job_key] = fact

        label = period or _weekly_period_label(period_end)
        snapshots = [
            self._build_snapshot(
                key,
                facts_by_job_key.values(),
                period=label,
                period_start=period_start,
                period_end=period_end,
            )
            for key, facts_by_job_key in grouped_facts.items()
        ]
        return sorted(snapshots, key=lambda snapshot: (snapshot.job_family_id, snapshot.location_id))

    def _snapshot_keys(self, fact: JobCategoryTrendJobFact) -> list[SnapshotKey]:
        if fact.taxonomy_version != self.taxonomy_service.taxonomy_version:
            return []

        location_ids = fact.location_ids or ["unknown-location"]
        return [
            (job_family_id, location_id)
            for job_family_id in self._eligible_job_family_ids(fact)
            for location_id in dict.fromkeys(location_ids)
        ]

    def _eligible_job_family_ids(self, fact: JobCategoryTrendJobFact) -> list[str]:
        job_family_ids: list[str] = []
        for job_category_id in fact.job_category_ids:
            definition = self.taxonomy_service.definitions_by_id.get(job_category_id)
            if definition and definition.trend_eligible and definition.job_family_id not in job_family_ids:
                job_family_ids.append(definition.job_family_id)
        return job_family_ids

    def _build_snapshot(
        self,
        key: SnapshotKey,
        facts: Iterable[JobCategoryTrendJobFact],
        *,
        period: str,
        period_start: date,
        period_end: date,
    ) -> JobFamilyTrendSnapshot:
        facts = list(facts)
        active_facts: list[JobCategoryTrendJobFact] = []
        unknown_active_count = 0
        updated_job_count = 0
        source_job_counts: Counter[str] = Counter()

        for fact in facts:
            source_job_counts[fact.source] += 1
            if _is_within_period(fact.source_updated_at, period_start, period_end):
                updated_job_count += 1

            activity = _is_active_at(fact, period_end)
            if activity is True:
                active_facts.append(fact)
            elif activity is None:
                unknown_active_count += 1

        job_family_id, location_id = key
        return JobFamilyTrendSnapshot(
            period=period,
            period_start=period_start,
            period_end=period_end,
            job_family_id=job_family_id,
            location_id=location_id,
            observed_job_count=len(facts),
            active_job_count=len(active_facts),
            unknown_active_job_count=unknown_active_count,
            updated_job_count=updated_job_count,
            distinct_company_count=len({fact.company_key for fact in active_facts if fact.company_key}),
            source_job_counts=dict(source_job_counts),
            taxonomy_version=self.taxonomy_service.taxonomy_version,
        )


def _is_newer_fact(candidate: JobCategoryTrendJobFact, existing: JobCategoryTrendJobFact) -> bool:
    candidate_rank = (
        candidate.source_updated_at or date.min,
        candidate.source_expires_at or date.min,
        candidate.content_hash,
    )
    existing_rank = (
        existing.source_updated_at or date.min,
        existing.source_expires_at or date.min,
        existing.content_hash,
    )
    return candidate_rank > existing_rank


def _is_active_at(fact: JobCategoryTrendJobFact, as_of_date: date) -> bool | None:
    if fact.source_expires_at is None:
        return None
    return fact.source_expires_at >= as_of_date


def _is_observable_by(fact: JobCategoryTrendJobFact, as_of_date: date) -> bool:
    return fact.source_updated_at is None or fact.source_updated_at <= as_of_date


def _is_within_period(value: date | None, period_start: date, period_end: date) -> bool:
    return value is not None and period_start <= value <= period_end


def _weekly_period_label(period_end: date) -> str:
    iso_year, iso_week, _ = period_end.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"
