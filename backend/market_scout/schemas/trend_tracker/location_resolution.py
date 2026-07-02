from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LocationResolution:
    location_id: str
    canonical_name: str
    matched_text: str
    confidence: str
    resolution_method: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "location_id": self.location_id,
            "canonical_name": self.canonical_name,
            "matched_text": self.matched_text,
            "confidence": self.confidence,
            "resolution_method": self.resolution_method,
        }
