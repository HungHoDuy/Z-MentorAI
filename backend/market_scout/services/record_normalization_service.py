from __future__ import annotations

from backend.market_scout.schemas import ExtractedSalaryRecord, ExtractedTrendRecord
from backend.market_scout.services.normalization_service import NormalizationService


class RecordNormalizationService:

    """Service for normalizing salary/trend records.
    Normalization includes standardizing job titles, locations, currencies, and calculating median salary."""
    def __init__(self, normalization_service: NormalizationService | None = None) -> None:
        self.normalization_service = normalization_service or NormalizationService()

    def normalize_salary_records(self, records: list[ExtractedSalaryRecord]) -> list[ExtractedSalaryRecord]:
        return [self.normalize_salary_record(record) for record in records]

    def normalize_trend_records(self, records: list[ExtractedTrendRecord]) -> list[ExtractedTrendRecord]:
        return [self.normalize_trend_record(record) for record in records]

    def normalize_salary_record(self, record: ExtractedSalaryRecord) -> ExtractedSalaryRecord:
        record.job_title = self.normalization_service.normalize_job_title(record.job_title) or record.job_title
        record.location = self.normalization_service.normalize_location(record.location)
        record.currency = self.normalization_service.normalize_currency(record.currency)
        record.salary_median = record.salary_median or (record.salary_min + record.salary_max) / 2
        record.metadata = {**record.metadata, "prepared": True}
        return record

    def normalize_trend_record(self, record: ExtractedTrendRecord) -> ExtractedTrendRecord:
        record.job_title = self.normalization_service.normalize_job_title(record.job_title)
        record.location = self.normalization_service.normalize_location(record.location)
        record.trend_type = record.trend_type.strip().lower()
        record.industry = self._normalize_industry(record.industry)
        record.metadata = {**record.metadata, "prepared": True}
        return record

    @staticmethod
    def _normalize_industry(industry: str | None) -> str | None:
        if not industry:
            return None

        aliases = {
            "ai/data": "AI/Data",
            "ai": "AI/Data",
            "data": "AI/Data",
            "cloud/devops": "Cloud/DevOps",
            "cybersecurity": "Cybersecurity",
            "product": "Product",
        }
        return aliases.get(industry.strip().lower(), industry.strip())
