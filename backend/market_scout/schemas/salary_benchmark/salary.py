from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


VND_MULTIPLIER = 1_000_000


@dataclass(frozen=True)
class SalarySearchQuery:
    raw_query: str
    job_title: str | None = None
    job_title_normalized: str | None = None
    location: str | None = None
    location_normalized: str | None = None
    experience_years: int | None = None
    currency: str = "VND"


@dataclass(frozen=True)
class SalaryJobRecord:
    job_id: str | None
    job_url: str | None
    company: str | None
    job_title: str
    locations: list[str]
    salary_min_vnd: int | None
    salary_max_vnd: int | None
    currency: str = "VND"
    period: str = "monthly"
    min_experience: int | None = None
    benefits: list[str] = field(default_factory=list)
    source_document_id: str | None = None

    @classmethod
    def from_firestore(cls, document_id: str, data: dict[str, Any]) -> "SalaryJobRecord | None":
        job_title = _clean_text(_first_value(data, ("job_title", "jobTitle", "title", "Tên công việc")))
        if not job_title:
            return None

        min_salary = _first_value(data, ("min_salary", "salary_min", "salary_min_vnd"))
        max_salary = _first_value(data, ("max_salary", "salary_max", "salary_max_vnd"))

        return cls(
            job_id=_clean_text(_first_value(data, ("job_id", "jobId", "id"))),
            job_url=_clean_text(_first_value(data, ("job_url", "jobUrl", "url", "link"))),
            company=_clean_text(_first_value(data, ("company", "company_name", "Công ty", "Tên công ty"))),
            job_title=job_title,
            locations=_normalize_locations(_first_value(data, ("location", "locations", "Địa điểm làm việc"))),
            salary_min_vnd=_salary_to_vnd(min_salary),
            salary_max_vnd=_salary_to_vnd(max_salary),
            currency="VND",
            period="monthly",
            min_experience=_to_int(_first_value(data, ("min_experience", "experience_min"))),
            benefits=_normalize_string_list(_first_value(data, ("benefits", "Phúc lợi", "Quyền lợi"))),
            source_document_id=document_id,
        )

    @property
    def has_salary(self) -> bool:
        return self.salary_min_vnd is not None and self.salary_max_vnd is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_url": self.job_url,
            "company": self.company,
            "job_title": self.job_title,
            "locations": self.locations,
            "salary_min_vnd": self.salary_min_vnd,
            "salary_max_vnd": self.salary_max_vnd,
            "currency": self.currency,
            "period": self.period,
            "min_experience": self.min_experience,
            "benefits": self.benefits,
            "source_document_id": self.source_document_id,
        }


def _first_value(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _normalize_locations(value: Any) -> list[str]:
    locations = _normalize_string_list(value)
    return locations


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        values = value
    elif isinstance(value, tuple | set):
        values = list(value)
    else:
        values = [value]

    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _clean_text(item)
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text)
    return normalized


def _salary_to_vnd(value: Any) -> int | None:
    number = _to_float(value)
    if number is None:
        return None

    # Cleaned crawler data currently stores salaries in million VND, e.g. 12 -> 12,000,000.
    if number < 1_000:
        number *= VND_MULTIPLIER

    return int(round(number))


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, int | float):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)

    text = str(value).strip().replace(",", ".")
    try:
        number = float(text)
    except ValueError:
        return None
    if math.isnan(number):
        return None
    return number


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    if number is None:
        return None
    return int(number)
