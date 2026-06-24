from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class JobCategoryTrendJobFact:
    """Normalized job fact for category-family demand snapshots and later enrichment."""

    job_key: str
    source: str
    source_job_id: str | None
    job_url: str | None
    canonical_job_url: str | None
    job_title: str
    company: str | None
    company_key: str | None
    location_ids: list[str]
    seniority: str | None
    employment_type: str | None
    source_updated_at: date | None
    source_expires_at: date | None
    is_active: bool | None
    content_hash: str
    requirements_text: str | None
    description_text: str | None
    raw_job_category_labels: list[str]
    job_category_ids: list[str]
    job_family_ids: list[str]
    unmatched_job_category_labels: list[str]
    invalid_job_category_labels: list[str]
    taxonomy_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_key": self.job_key,
            "source": self.source,
            "source_job_id": self.source_job_id,
            "job_url": self.job_url,
            "canonical_job_url": self.canonical_job_url,
            "job_title": self.job_title,
            "company": self.company,
            "company_key": self.company_key,
            "location_ids": list(self.location_ids),
            "seniority": self.seniority,
            "employment_type": self.employment_type,
            "source_updated_at": self.source_updated_at.isoformat() if self.source_updated_at else None,
            "source_expires_at": self.source_expires_at.isoformat() if self.source_expires_at else None,
            "is_active": self.is_active,
            "content_hash": self.content_hash,
            "requirements_text": self.requirements_text,
            "description_text": self.description_text,
            "raw_job_category_labels": list(self.raw_job_category_labels),
            "job_category_ids": list(self.job_category_ids),
            "job_family_ids": list(self.job_family_ids),
            "unmatched_job_category_labels": list(self.unmatched_job_category_labels),
            "invalid_job_category_labels": list(self.invalid_job_category_labels),
            "taxonomy_version": self.taxonomy_version,
        }
