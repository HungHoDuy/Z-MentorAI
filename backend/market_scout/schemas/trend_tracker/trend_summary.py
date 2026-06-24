from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TrendSummaryResult:
    answer: str
    confidence: str
    sources: list[dict[str, Any]]
    limitations: list[str]
    composer_version: str = "trend-summary-v1"

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "confidence": self.confidence,
            "sources": [dict(source) for source in self.sources],
            "limitations": list(self.limitations),
            "composer_version": self.composer_version,
        }
