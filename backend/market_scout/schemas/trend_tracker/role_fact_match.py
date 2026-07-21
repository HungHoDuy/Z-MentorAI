from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RoleFactMatch:
    """A job fact candidate matched from a natural-language role query."""

    job_key: str
    job_title: str
    company: str | None = None
    job_url: str | None = None
    job_category_ids: list[str] = None
    job_family_ids: list[str] = None
    location_ids: list[str] = None
    is_active: bool | None = None
    score: float = 0.0
    match_method: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_key": self.job_key,
            "job_title": self.job_title,
            "company": self.company,
            "job_url": self.job_url,
            "job_category_ids": list(self.job_category_ids or []),
            "job_family_ids": list(self.job_family_ids or []),
            "location_ids": list(self.location_ids or []),
            "is_active": self.is_active,
            "score": round(self.score, 4),
            "match_method": self.match_method,
        }