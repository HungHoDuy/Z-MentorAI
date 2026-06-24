from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class AutomationRiskLookup:
    job_category_id: str
    exposure_level: str
    risk_reason: str
    protected_tasks: list[str]
    at_risk_tasks: list[str]
    source_title: str
    source_url: str
    published_at: date | None
    caveat: str


@dataclass(frozen=True)
class AutomationExposureSignal:
    signal: str
    job_category_id: str
    exposure_level: str | None
    risk_reason: str | None
    protected_tasks: list[str]
    at_risk_tasks: list[str]
    confidence: str
    source_url: str | None
    limitations: list[str]
