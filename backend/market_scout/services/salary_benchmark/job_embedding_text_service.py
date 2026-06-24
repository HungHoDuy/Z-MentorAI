from __future__ import annotations

from typing import Any

from backend.market_scout.schemas.salary import SalaryJobRecord


class JobEmbeddingTextService:
    """Build stable text input for embedding a job posting."""

    REQUIREMENT_FIELDS = (
        "Yêu Cầu Công Việc",
        "Yêu cầu công việc",
        "requirements",
        "job_requirements",
    )
    OTHER_INFO_FIELDS = (
        "Thông tin khác",
        "Thông Tin Khác",
        "other_info",
    )

    def build_text(self, document_id: str, data: dict[str, Any]) -> str | None:
        record = SalaryJobRecord.from_firestore(document_id, data)
        if record is None:
            return None

        requirements = _clean_text(_first_value(data, self.REQUIREMENT_FIELDS))
        other_info = _clean_text(_first_value(data, self.OTHER_INFO_FIELDS))

        parts = [
            ("Job title", record.job_title),
            ("Company", record.company),
            ("Location", ", ".join(record.locations)),
            ("Minimum experience", f"{record.min_experience} years" if record.min_experience is not None else None),
            (
                "Salary",
                self._salary_text(record),
            ),
            ("Benefits", ", ".join(record.benefits)),
            ("Other info", other_info),
            ("Requirements", requirements),
        ]

        lines = [f"{label}: {value}" for label, value in parts if value]
        return "\n".join(lines).strip() or None

    @staticmethod
    def _salary_text(record: SalaryJobRecord) -> str | None:
        if record.salary_min_vnd is None or record.salary_max_vnd is None:
            return None

        min_salary = round(record.salary_min_vnd / 1_000_000, 2)
        max_salary = round(record.salary_max_vnd / 1_000_000, 2)
        return f"{min_salary:g} - {max_salary:g} million VND per month"


def _first_value(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value if item not in (None, ""))
    elif isinstance(value, dict):
        value = " ".join(str(item) for item in value.values() if item not in (None, ""))

    text = " ".join(str(value).split())
    return text or None
