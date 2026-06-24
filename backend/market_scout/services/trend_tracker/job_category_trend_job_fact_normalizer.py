from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from backend.market_scout.schemas.trend_tracker.job_category_trend import JobCategoryTrendJobFact
from backend.market_scout.services.trend_tracker.job_category_taxonomy_service import JobCategoryTaxonomyService
from backend.market_scout.services.trend_tracker.trend_job_fact_normalizer import TrendJobFactNormalizer


class JobCategoryTrendJobFactNormalizer:
    """Normalize a raw job document without imposing role or skill dimensions."""

    def __init__(
        self,
        *,
        base_normalizer: TrendJobFactNormalizer | None = None,
        taxonomy_service: JobCategoryTaxonomyService | None = None,
    ) -> None:
        self.base_normalizer = base_normalizer or TrendJobFactNormalizer()
        self.taxonomy_service = taxonomy_service or JobCategoryTaxonomyService()

    def normalize(
        self,
        document_id: str,
        data: Mapping[str, Any],
        *,
        observed_at: date | datetime | None = None,
    ) -> JobCategoryTrendJobFact | None:
        base_fact = self.base_normalizer.normalize(
            document_id,
            data,
            observed_at=observed_at,
        )
        if base_fact is None:
            return None

        raw_labels = self.taxonomy_service.extract_raw_labels(data)
        match = self.taxonomy_service.classify(raw_labels)
        return JobCategoryTrendJobFact(
            job_key=base_fact.job_key,
            source=base_fact.source,
            source_job_id=base_fact.source_job_id,
            job_url=base_fact.job_url,
            canonical_job_url=base_fact.canonical_job_url,
            job_title=base_fact.job_title,
            company=base_fact.company,
            company_key=base_fact.company_key,
            location_ids=base_fact.location_ids,
            seniority=base_fact.seniority,
            employment_type=base_fact.employment_type,
            source_updated_at=base_fact.source_updated_at,
            source_expires_at=base_fact.source_expires_at,
            is_active=base_fact.is_active,
            content_hash=_content_hash(
                job_title=base_fact.job_title,
                company=base_fact.company,
                location_ids=base_fact.location_ids,
                raw_job_category_labels=match.raw_labels,
                requirements_text=base_fact.requirements_text,
                description_text=base_fact.description_text,
            ),
            requirements_text=base_fact.requirements_text,
            description_text=base_fact.description_text,
            raw_job_category_labels=match.raw_labels,
            job_category_ids=match.job_category_ids,
            job_family_ids=match.job_family_ids,
            unmatched_job_category_labels=match.unmatched_labels,
            invalid_job_category_labels=match.invalid_labels,
            taxonomy_version=match.taxonomy_version,
        )


def _content_hash(
    *,
    job_title: str,
    company: str | None,
    location_ids: list[str],
    raw_job_category_labels: list[str],
    requirements_text: str | None,
    description_text: str | None,
) -> str:
    parts = (
        ("job_title", job_title),
        ("company", company or ""),
        ("locations", "|".join(sorted(location_ids))),
        ("raw_job_categories", "|".join(sorted(raw_job_category_labels))),
        ("requirements", requirements_text or ""),
        ("description", description_text or ""),
    )
    payload = "\n".join(f"{name}: {value}" for name, value in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
