from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from backend.market_scout.schemas.salary import SalaryJobRecord, SalarySearchQuery
from backend.market_scout.services.salary_query_normalizer import SalaryQueryNormalizer


@dataclass(frozen=True)
class SalaryRange:
    min: int
    max: int
    currency: str = "VND"
    period: str = "monthly"

    def to_dict(self) -> dict[str, Any]:
        return {
            "min": self.min,
            "max": self.max,
            "currency": self.currency,
            "period": self.period,
        }


@dataclass(frozen=True)
class SalaryBenchmarkSource:
    company: str | None
    job_title: str
    job_url: str | None
    salary_min_vnd: int
    salary_max_vnd: int
    distance: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": self.company,
            "job_title": self.job_title,
            "job_url": self.job_url,
            "salary_min_vnd": self.salary_min_vnd,
            "salary_max_vnd": self.salary_max_vnd,
            "distance": self.distance,
        }


@dataclass(frozen=True)
class SalaryBenchmarkResult:
    job_title: str | None
    location: str | None
    experience_years: int | None
    salary_range: SalaryRange | None
    sample_size: int
    confidence: str
    sources: list[SalaryBenchmarkSource]
    average_distance: float | None = None
    discarded_outliers: int = 0
    matched_records: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_title": self.job_title,
            "location": self.location,
            "experience_years": self.experience_years,
            "salary_range": self.salary_range.to_dict() if self.salary_range else None,
            "sample_size": self.sample_size,
            "confidence": self.confidence,
            "average_distance": round(self.average_distance, 4) if self.average_distance is not None else None,
            "sources": [source.to_dict() for source in self.sources],
            "discarded_outliers": self.discarded_outliers,
            "matched_records": self.matched_records,
        }


@dataclass(frozen=True)
class _SalarySample:
    record: SalaryJobRecord
    distance: float | None

    @property
    def midpoint(self) -> float:
        return (self.record.salary_min_vnd + self.record.salary_max_vnd) / 2


class SalaryBenchmarkService:
    """Aggregate salary benchmark statistics from vector-search job matches."""

    def __init__(
        self,
        *,
        normalizer: SalaryQueryNormalizer | None = None,
        min_salary_vnd: int = 3_000_000,
        max_salary_vnd: int = 300_000_000,
        source_limit: int = 5,
        round_to_vnd: int = 100_000,
        high_confidence_distance: float = 0.2,
        medium_confidence_distance: float = 0.35,
    ) -> None:
        self.normalizer = normalizer or SalaryQueryNormalizer()
        self.min_salary_vnd = min_salary_vnd
        self.max_salary_vnd = max_salary_vnd
        self.source_limit = source_limit
        self.round_to_vnd = round_to_vnd
        self.high_confidence_distance = high_confidence_distance
        self.medium_confidence_distance = medium_confidence_distance

    def aggregate(
        self,
        query: SalarySearchQuery | str,
        search_results: Iterable[Any],
    ) -> SalaryBenchmarkResult:
        search_query = self.normalizer.extract(query) if isinstance(query, str) else query
        samples = self._valid_samples(search_results)
        filtered_samples = self._remove_midpoint_outliers(samples)
        discarded_outliers = len(samples) - len(filtered_samples)

        if not filtered_samples:
            return SalaryBenchmarkResult(
                job_title=search_query.job_title,
                location=search_query.location,
                experience_years=search_query.experience_years,
                salary_range=None,
                sample_size=0,
                confidence="low",
                sources=[],
                average_distance=None,
                discarded_outliers=discarded_outliers,
                matched_records=len(samples),
            )

        avg_min = sum(sample.record.salary_min_vnd for sample in filtered_samples) / len(filtered_samples)
        avg_max = sum(sample.record.salary_max_vnd for sample in filtered_samples) / len(filtered_samples)
        salary_min = self._round_salary(avg_min)
        salary_max = self._round_salary(avg_max)
        if salary_min > salary_max:
            salary_min, salary_max = salary_max, salary_min

        average_distance = self._average_distance(filtered_samples)
        return SalaryBenchmarkResult(
            job_title=search_query.job_title,
            location=search_query.location,
            experience_years=search_query.experience_years,
            salary_range=SalaryRange(min=salary_min, max=salary_max),
            sample_size=len(filtered_samples),
            confidence=self._confidence(average_distance),
            sources=self._sources(filtered_samples),
            average_distance=average_distance,
            discarded_outliers=discarded_outliers,
            matched_records=len(samples),
        )

    def _valid_samples(self, search_results: Iterable[Any]) -> list[_SalarySample]:
        samples: list[_SalarySample] = []
        for result in search_results:
            record = result.record
            if record.salary_min_vnd is None or record.salary_max_vnd is None:
                continue
            if record.salary_min_vnd <= 0 or record.salary_max_vnd <= 0:
                continue
            if record.salary_min_vnd > record.salary_max_vnd:
                continue
            if record.salary_min_vnd < self.min_salary_vnd:
                continue
            if record.salary_max_vnd > self.max_salary_vnd:
                continue
            samples.append(_SalarySample(record=record, distance=result.distance))
        return samples

    def _remove_midpoint_outliers(self, samples: list[_SalarySample]) -> list[_SalarySample]:
        if len(samples) < 4:
            return samples

        midpoints = sorted(sample.midpoint for sample in samples)
        q1 = _percentile(midpoints, 0.25)
        q3 = _percentile(midpoints, 0.75)
        iqr = q3 - q1
        if iqr <= 0:
            return samples

        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        filtered = [sample for sample in samples if lower_bound <= sample.midpoint <= upper_bound]
        return filtered or samples

    def _sources(self, samples: list[_SalarySample]) -> list[SalaryBenchmarkSource]:
        sorted_samples = sorted(samples, key=lambda sample: sample.distance if sample.distance is not None else 999)
        sources: list[SalaryBenchmarkSource] = []
        for sample in sorted_samples[: self.source_limit]:
            record = sample.record
            sources.append(
                SalaryBenchmarkSource(
                    company=record.company,
                    job_title=record.job_title,
                    job_url=record.job_url,
                    salary_min_vnd=record.salary_min_vnd,
                    salary_max_vnd=record.salary_max_vnd,
                    distance=sample.distance,
                )
            )
        return sources

    def _confidence(self, average_distance: float | None) -> str:
        if average_distance is None:
            return "low"
        if average_distance <= self.high_confidence_distance:
            return "high"
        if average_distance <= self.medium_confidence_distance:
            return "medium"
        return "low"

    @staticmethod
    def _average_distance(samples: list[_SalarySample]) -> float | None:
        distances = [sample.distance for sample in samples if sample.distance is not None]
        if not distances:
            return None
        return sum(distances) / len(distances)

    def _round_salary(self, value: float) -> int:
        return int(round(value / self.round_to_vnd) * self.round_to_vnd)


def _percentile(sorted_values: list[float], percentile: float) -> float:
    if not sorted_values:
        raise ValueError("Cannot calculate percentile for an empty list.")
    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (len(sorted_values) - 1) * percentile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    weight = position - lower_index
    return sorted_values[lower_index] * (1 - weight) + sorted_values[upper_index] * weight
