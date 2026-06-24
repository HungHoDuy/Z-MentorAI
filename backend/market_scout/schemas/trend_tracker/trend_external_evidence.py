from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class TrendSource:
    source_id: str
    source_name: str
    publisher: str
    source_type: str
    published_at: date
    fetched_at: date
    reliability_score: float
    scope_location_ids: list[str]
    scope_period: str | None
    url: str
    content_hash: str | None
    notes: str | None


@dataclass(frozen=True)
class TrendEvidence:
    evidence_id: str
    source_id: str
    job_family_ids: list[str]
    job_category_ids: list[str]
    location_ids: list[str]
    period: str | None
    direction: str
    exact_claim: str
    metric_value: float | None
    metric_unit: str | None
    citation: str
    confidence: str


@dataclass(frozen=True)
class TrendEvidenceMatch:
    source: TrendSource
    evidence: TrendEvidence
