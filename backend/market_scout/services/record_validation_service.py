from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, TypeVar

from backend.market_scout.schemas import ExtractedSalaryRecord, ExtractedTrendRecord

T = TypeVar("T")


@dataclass
class ValidationResult(Generic[T]):
    valid_records: list[T] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


class RecordValidationService:
    
    """Service for validating salary/trend records.
    Salary records must have a valid job title, positive salary range, valid currency, and source URL.
    Trend records must have a market signal, valid trend type, and source URL."""

    VALID_TREND_TYPES = {"growth", "decline", "demand", "risk"}
    VALID_CURRENCIES = {"VND", "USD"}

    def validate_salary_records(self, records: list[ExtractedSalaryRecord]) -> ValidationResult[ExtractedSalaryRecord]:
        result: ValidationResult[ExtractedSalaryRecord] = ValidationResult()

        for index, record in enumerate(records):
            errors = self._salary_errors(record)
            if errors:
                result.errors.append({"index": index, "record": record.to_dict(), "errors": errors})
            else:
                result.valid_records.append(record)

        return result

    def validate_trend_records(self, records: list[ExtractedTrendRecord]) -> ValidationResult[ExtractedTrendRecord]:
        result: ValidationResult[ExtractedTrendRecord] = ValidationResult()

        for index, record in enumerate(records):
            errors = self._trend_errors(record)
            if errors:
                result.errors.append({"index": index, "record": record.to_dict(), "errors": errors})
            else:
                result.valid_records.append(record)

        return result

    def _salary_errors(self, record: ExtractedSalaryRecord) -> list[str]:
        errors: list[str] = []

        if not record.job_title or record.job_title.lower() == "unknown":
            errors.append("job_title is missing or unknown")
        if record.salary_min <= 0:
            errors.append("salary_min must be greater than 0")
        if record.salary_max <= 0:
            errors.append("salary_max must be greater than 0")
        if record.salary_min > record.salary_max:
            errors.append("salary_min must be less than or equal to salary_max")
        if record.currency not in self.VALID_CURRENCIES:
            errors.append(f"currency must be one of {sorted(self.VALID_CURRENCIES)}")
        if not record.source.url:
            errors.append("source.url is missing")

        return errors

    def _trend_errors(self, record: ExtractedTrendRecord) -> list[str]:
        errors: list[str] = []

        if not record.market_signal:
            errors.append("market_signal is missing")
        if record.trend_type not in self.VALID_TREND_TYPES:
            errors.append(f"trend_type must be one of {sorted(self.VALID_TREND_TYPES)}")
        if not record.source.url:
            errors.append("source.url is missing")

        return errors
