from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class TrendQueryIntent(str, Enum):
    CURRENT_DEMAND = "current_demand"
    CURRENT_SKILL_DEMAND = "current_skill_demand"
    AUTOMATION_EXPOSURE = "automation_exposure"
    EXTERNAL_OUTLOOK = "external_outlook"
    DEMAND_PRESSURE = "demand_pressure"


@dataclass(frozen=True)
class TrendQueryInput:
    intent: TrendQueryIntent | str
    job_family_id: str | None = None
    job_category_id: str | None = None
    job_category: str | None = None
    location_id: str | None = None
    location: str | None = None


@dataclass(frozen=True)
class TrendQuery:
    """Canonical MVP query used to retrieve job-family trend snapshots."""

    intent: TrendQueryIntent
    job_family_id: str
    location_id: str
    job_category_id: str | None = None
