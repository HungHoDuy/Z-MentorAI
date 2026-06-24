from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any


@dataclass(frozen=True)
class TrendJobFact:
    """Compatibility contract used by the shared raw-job parser during v2 migration."""

    job_key: str
    source: str
    source_job_id: str | None
    job_url: str | None
    canonical_job_url: str | None
    job_title: str
    role_id: str
    industry_ids: list[str]
    location_ids: list[str]
    company: str | None
    company_key: str | None
    seniority: str | None
    employment_type: str | None
    source_updated_at: date | None
    source_expires_at: date | None
    is_active: bool | None
    skill_ids: list[str]
    content_hash: str
    requirements_text: str | None
    description_text: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_key": self.job_key,
            "source": self.source,
            "source_job_id": self.source_job_id,
            "job_url": self.job_url,
            "canonical_job_url": self.canonical_job_url,
            "job_title": self.job_title,
            "role_id": self.role_id,
            "industry_ids": list(self.industry_ids),
            "location_ids": list(self.location_ids),
            "company": self.company,
            "company_key": self.company_key,
            "seniority": self.seniority,
            "employment_type": self.employment_type,
            "source_updated_at": self.source_updated_at.isoformat() if self.source_updated_at else None,
            "source_expires_at": self.source_expires_at.isoformat() if self.source_expires_at else None,
            "is_active": self.is_active,
            "skill_ids": list(self.skill_ids),
            "content_hash": self.content_hash,
            "requirements_text": self.requirements_text,
            "description_text": self.description_text,
        }
