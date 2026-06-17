from __future__ import annotations

import hashlib

from backend.market_scout.schemas import ExtractedSalaryRecord, ExtractedTrendRecord


class RecordDeduplicationService:

    """Service for deduplicating salary/trend records.
    With salary records, duplicates are identified if they have the same source URL, job title, location, experience range, salary range, currency, and period.
    With trend records, duplicates are identified if they have the same source URL, job title, industry, trend type, time horizon, and market signal."""

    def deduplicate_salary_records(self, records: list[ExtractedSalaryRecord]) -> list[ExtractedSalaryRecord]:
        seen: set[tuple] = set()
        deduped: list[ExtractedSalaryRecord] = []

        for record in records:
            key = (
                record.source.url,
                record.job_title.lower(),
                (record.location or "").lower(),
                record.experience_min,
                record.experience_max,
                round(record.salary_min, 2),
                round(record.salary_max, 2),
                record.currency,
                record.period.value,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)

        return deduped

    def deduplicate_trend_records(self, records: list[ExtractedTrendRecord]) -> list[ExtractedTrendRecord]:
        seen: set[tuple] = set()
        deduped: list[ExtractedTrendRecord] = []

        for record in records:
            signal_hash = hashlib.sha256(record.market_signal.lower().encode("utf-8")).hexdigest()
            key = (
                record.source.url,
                (record.job_title or "").lower(),
                (record.industry or "").lower(),
                record.trend_type,
                record.time_horizon,
                signal_hash,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)

        return deduped
