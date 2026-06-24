from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HybridSignalResult:
    """Deterministic evidence payload for the Trend Tracker response layer."""

    intent: str
    signal: str
    job_family_id: str
    job_category_id: str | None
    location_id: str
    snapshot_id: str | None
    period: str | None
    confidence: str
    directional_trend: bool
    data: dict[str, Any]
    sources: list[dict[str, Any]]
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "signal": self.signal,
            "job_family_id": self.job_family_id,
            "job_category_id": self.job_category_id,
            "location_id": self.location_id,
            "snapshot_id": self.snapshot_id,
            "period": self.period,
            "confidence": self.confidence,
            "directional_trend": self.directional_trend,
            "data": dict(self.data),
            "sources": [dict(source) for source in self.sources],
            "limitations": list(self.limitations),
        }
