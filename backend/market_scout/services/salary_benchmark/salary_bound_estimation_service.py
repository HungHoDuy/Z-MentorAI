from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any

from backend.market_scout.schemas.salary_benchmark.salary import SalaryJobRecord


VND_MULTIPLIER = 1_000_000


@dataclass(frozen=True)
class SalaryBoundEstimate:
    salary_min_vnd: int
    salary_max_vnd: int
    min_salary: float
    max_salary: float
    salary_factor: float


class SalaryBoundEstimationService:
    """Estimate open-ended salary bounds with the median range factor."""

    def __init__(
        self,
        *,
        min_factor: float = 1.05,
        max_factor: float = 3.0,
        fallback_factor: float = 1.5,
        min_sentinel_count: int = 20,
    ) -> None:
        self.min_factor = min_factor
        self.max_factor = max_factor
        self.fallback_factor = fallback_factor
        self.min_sentinel_count = min_sentinel_count

    def detect_max_salary_sentinel(self, documents: list[tuple[str, dict[str, Any]]]) -> int | None:
        counts: dict[int, int] = {}

        for document_id, data in documents:
            record = SalaryJobRecord.from_firestore(document_id, data)
            if record is None:
                continue

            max_vnd = record.salary_max_vnd
            if max_vnd is None or max_vnd <= 0:
                continue
            counts[max_vnd] = counts.get(max_vnd, 0) + 1

        if not counts:
            return None

        max_salary_vnd = max(counts)
        if counts[max_salary_vnd] >= self.min_sentinel_count:
            return max_salary_vnd
        return None

    def calculate_factor(
        self,
        documents: list[tuple[str, dict[str, Any]]],
        *,
        max_salary_sentinel_vnd: int | None = None,
    ) -> float:
        factors: list[float] = []

        for document_id, data in documents:
            record = SalaryJobRecord.from_firestore(document_id, data)
            if record is None:
                continue

            min_vnd = record.salary_min_vnd
            max_vnd = record.salary_max_vnd
            if min_vnd is None or max_vnd is None:
                continue
            if max_salary_sentinel_vnd is not None and max_vnd == max_salary_sentinel_vnd:
                continue
            if min_vnd <= 0 or max_vnd <= 0 or max_vnd < min_vnd:
                continue

            factor = max_vnd / min_vnd
            if self.min_factor <= factor <= self.max_factor:
                factors.append(factor)

        if not factors:
            return self.fallback_factor

        return round(median(factors), 4)

    def estimate(
        self,
        document_id: str,
        data: dict[str, Any],
        salary_factor: float,
        *,
        max_salary_sentinel_vnd: int | None = None,
    ) -> SalaryBoundEstimate | None:
        record = SalaryJobRecord.from_firestore(document_id, data)
        if record is None:
            return None

        min_vnd = record.salary_min_vnd
        max_vnd = record.salary_max_vnd
        max_is_sentinel = max_salary_sentinel_vnd is not None and max_vnd == max_salary_sentinel_vnd

        has_min = min_vnd is not None and min_vnd > 0
        has_max = max_vnd is not None and max_vnd > 0 and not max_is_sentinel

        if not has_min and has_max:
            min_vnd = int(round(max_vnd / salary_factor))
        elif has_min and not has_max:
            max_vnd = int(round(min_vnd * salary_factor))
        else:
            return None

        if min_vnd <= 0 or max_vnd <= 0:
            return None
        if min_vnd > max_vnd:
            min_vnd, max_vnd = max_vnd, min_vnd

        return SalaryBoundEstimate(
            salary_min_vnd=min_vnd,
            salary_max_vnd=max_vnd,
            min_salary=round(min_vnd / VND_MULTIPLIER, 2),
            max_salary=round(max_vnd / VND_MULTIPLIER, 2),
            salary_factor=salary_factor,
        )
