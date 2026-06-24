from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JobCategoryDefinition:
    """One canonical CareerViet job category and its broad job family."""

    job_category_id: str
    label: str
    job_family_id: str
    trend_eligible: bool = True
    cross_cutting: bool = False


@dataclass(frozen=True)
class JobCategoryTaxonomyMatch:
    raw_labels: list[str]
    job_category_ids: list[str]
    job_family_ids: list[str]
    unmatched_labels: list[str]
    invalid_labels: list[str]
    taxonomy_version: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_labels": list(self.raw_labels),
            "job_category_ids": list(self.job_category_ids),
            "job_family_ids": list(self.job_family_ids),
            "unmatched_labels": list(self.unmatched_labels),
            "invalid_labels": list(self.invalid_labels),
            "taxonomy_version": self.taxonomy_version,
        }
