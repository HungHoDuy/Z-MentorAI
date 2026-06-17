from __future__ import annotations

from pathlib import Path

from backend.market_scout.repositories import SalaryRecordRepository, TrendRecordRepository
from backend.market_scout.schemas import ExtractedSalaryRecord, ExtractedTrendRecord
from backend.market_scout.services import (
    RecordDeduplicationService,
    RecordNormalizationService,
    RecordValidationService,
)


class PrepareRecordsPipeline:

    """Read salary_records.jsonl and trend_records.jsonl:
Normalize.
Validate.
Deduplicate.
"""
    def __init__(
        self,
        salary_record_repository: SalaryRecordRepository | None = None,
        trend_record_repository: TrendRecordRepository | None = None,
        prepared_salary_repository: SalaryRecordRepository | None = None,
        prepared_trend_repository: TrendRecordRepository | None = None,
        validation_service: RecordValidationService | None = None,
        normalization_service: RecordNormalizationService | None = None,
        deduplication_service: RecordDeduplicationService | None = None,
    ) -> None:
        self.salary_record_repository = salary_record_repository or SalaryRecordRepository()
        self.trend_record_repository = trend_record_repository or TrendRecordRepository()
        self.prepared_salary_repository = prepared_salary_repository or SalaryRecordRepository(self._prepared_salary_path())
        self.prepared_trend_repository = prepared_trend_repository or TrendRecordRepository(self._prepared_trend_path())
        self.validation_service = validation_service or RecordValidationService()
        self.normalization_service = normalization_service or RecordNormalizationService()
        self.deduplication_service = deduplication_service or RecordDeduplicationService()

    async def run(
        self,
        salary_records: list[ExtractedSalaryRecord] | None = None,
        trend_records: list[ExtractedTrendRecord] | None = None,
        *,
        save_records: bool = True,
        overwrite: bool = True,
    ) -> dict:
        raw_salary_records = salary_records if salary_records is not None else await self.salary_record_repository.load_all()
        raw_trend_records = trend_records if trend_records is not None else await self.trend_record_repository.load_all()

        normalized_salary = self.normalization_service.normalize_salary_records(raw_salary_records)
        normalized_trend = self.normalization_service.normalize_trend_records(raw_trend_records)

        salary_validation = self.validation_service.validate_salary_records(normalized_salary)
        trend_validation = self.validation_service.validate_trend_records(normalized_trend)

        prepared_salary = self.deduplication_service.deduplicate_salary_records(salary_validation.valid_records)
        prepared_trend = self.deduplication_service.deduplicate_trend_records(trend_validation.valid_records)

        saved_salary_records = 0
        saved_trend_records = 0
        if save_records:
            saved_salary_records = await self.prepared_salary_repository.save_many(prepared_salary, overwrite=overwrite)
            saved_trend_records = await self.prepared_trend_repository.save_many(prepared_trend, overwrite=overwrite)

        return {
            "status": "success",
            "salary": {
                "input_records": len(raw_salary_records),
                "valid_records": len(salary_validation.valid_records),
                "prepared_records": len(prepared_salary),
                "saved_records": saved_salary_records,
                "invalid_records": len(salary_validation.errors),
                "errors": salary_validation.errors,
                "records": [record.to_dict() for record in prepared_salary],
            },
            "trend": {
                "input_records": len(raw_trend_records),
                "valid_records": len(trend_validation.valid_records),
                "prepared_records": len(prepared_trend),
                "saved_records": saved_trend_records,
                "invalid_records": len(trend_validation.errors),
                "errors": trend_validation.errors,
                "records": [record.to_dict() for record in prepared_trend],
            },
        }

    @staticmethod
    def _storage_dir() -> Path:
        return Path(__file__).resolve().parents[1] / "storage"

    def _prepared_salary_path(self) -> Path:
        return self._storage_dir() / "prepared_salary_records.jsonl"

    def _prepared_trend_path(self) -> Path:
        return self._storage_dir() / "prepared_trend_records.jsonl"
