from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.market_scout.schemas.trend_tracker.role_fact_match import RoleFactMatch


@dataclass(frozen=True)
class RoleResolutionResult:
    """Aggregated role-to-category/family resolution with confidence gates."""

    resolved_job_category_id: str | None
    resolved_job_family_id: str | None
    confidence: str
    accepted: bool
    top_score: float
    matched_fact_count: int
    category_score_share: float
    location_match_share: float | None
    rejection_reason: str | None
    matches: list[RoleFactMatch]

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolved_job_category_id": self.resolved_job_category_id,
            "resolved_job_family_id": self.resolved_job_family_id,
            "confidence": self.confidence,
            "accepted": self.accepted,
            "top_score": round(self.top_score, 4),
            "matched_fact_count": self.matched_fact_count,
            "category_score_share": round(self.category_score_share, 4),
            "location_match_share": round(self.location_match_share, 4) if self.location_match_share is not None else None,
            "rejection_reason": self.rejection_reason,
            "matches": [match.to_dict() for match in self.matches],
        }