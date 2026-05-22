from dataclasses import asdict, dataclass
from typing import Any

from .enums import SalaryPeriod, SeniorityLevel


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


@dataclass
class SalaryRange:
    min: float | None = None
    max: float | None = None
    median: float | None = None
    currency: str = "VND"
    period: SalaryPeriod = SalaryPeriod.MONTHLY

    def __post_init__(self) -> None:
        self.currency = self.currency.upper().strip()

        if isinstance(self.period, str):
            self.period = SalaryPeriod(self.period)

        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("Salary range min must be less than or equal to max.")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["period"] = _enum_value(self.period)
        return data


@dataclass
class MarketScoutEntities:
    job_title: str | None = None
    industry: str | None = None
    location: str | None = None
    experience_years: int | None = None
    seniority: SeniorityLevel | None = None
    currency: str = "VND"
    time_horizon: str | None = None
    target_role: str | None = None
    skills: list[str] | None = None
    salary_period: SalaryPeriod = SalaryPeriod.MONTHLY

    def __post_init__(self) -> None:
        self.job_title = self._clean_optional_text(self.job_title)
        self.industry = self._clean_optional_text(self.industry)
        self.location = self._clean_optional_text(self.location)
        self.target_role = self._clean_optional_text(self.target_role)
        self.time_horizon = self._clean_optional_text(self.time_horizon)
        self.currency = self.currency.upper().strip()

        if isinstance(self.seniority, str):
            self.seniority = SeniorityLevel(self.seniority)

        if isinstance(self.salary_period, str):
            self.salary_period = SalaryPeriod(self.salary_period)

        if self.experience_years is not None and self.experience_years < 0:
            raise ValueError("Experience years must be greater than or equal to 0.")

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None

        cleaned = value.strip()
        return cleaned or None

    def has_salary_context(self) -> bool:
        return bool(self.job_title and self.location)

    def has_trend_context(self) -> bool:
        return bool(self.industry or self.job_title or self.target_role)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["seniority"] = _enum_value(self.seniority)
        data["salary_period"] = _enum_value(self.salary_period)
        return data
