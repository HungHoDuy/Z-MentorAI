from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RoleFactMatch:
    """A job fact candidate matched from a natural-language role query."""

    job_key: str
    job_title: str
    job_category_ids: list[str]
    job_family_ids: list[str]
    location_ids: list[str]
    score: float
    match_method: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_key": self.job_key,
            "job_title": self.job_title,
            "job_category_ids": list(self.job_category_ids),
            "job_family_ids": list(self.job_family_ids),
            "location_ids": list(self.location_ids),
            "score": round(self.score, 4),
            "match_method": self.match_method,
        }