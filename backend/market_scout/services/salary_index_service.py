from __future__ import annotations

from typing import Any

from backend.market_scout.schemas.salary import SalaryJobRecord
from backend.market_scout.services.salary_query_normalizer import SalaryQueryNormalizer


class SalaryIndexService:
    """Build Firestore-side search index fields for salary benchmark queries."""

    def __init__(
        self,
        normalizer: SalaryQueryNormalizer | None = None,
        *,
        max_title_search_keys: int = 50,
    ) -> None:
        self.normalizer = normalizer or SalaryQueryNormalizer(max_title_search_keys=max_title_search_keys)

    def build_index_fields(self, document_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        record = SalaryJobRecord.from_firestore(document_id, data)
        if record is None:
            return None

        title_normalized = self.normalizer.normalize_job_title(record.job_title)
        title_search_keys = self.normalizer.build_title_search_keys(record.job_title)
        location_normalized = self.normalizer.build_location_search_keys(record.locations)
        salary_search_keys = self.normalizer.build_salary_search_keys(record.job_title, record.locations)

        return {
            "job_title_normalized": title_normalized,
            "job_title_search_keys": title_search_keys,
            "location_normalized": location_normalized,
            "salary_search_keys": salary_search_keys,
            "salary_min_vnd": record.salary_min_vnd,
            "salary_max_vnd": record.salary_max_vnd,
            "currency": record.currency,
            "period": record.period,
        }
