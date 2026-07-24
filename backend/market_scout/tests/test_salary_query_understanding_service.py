import json

from backend.market_scout.services.salary_benchmark.salary_query_understanding_service import (
    SalaryQueryUnderstandingService,
)


class FakeLlm:
    def __init__(self, payload: dict | Exception) -> None:
        self.payload = payload
        self.calls = []

    def invoke(self, input, **kwargs):
        self.calls.append(input)
        if isinstance(self.payload, Exception):
            raise self.payload
        return json.dumps(self.payload, ensure_ascii=False)


def test_extracts_salary_query_from_llm_structured_output() -> None:
    llm = FakeLlm(
        {
            "job_title": "Business Analyst",
            "location": "Ha Noi",
            "experience_years": 3,
            "currency": "VND",
            "confidence": "high",
        }
    )
    service = SalaryQueryUnderstandingService(llm=llm)

    result = service.extract("Luong Business Analyst tai Ha Noi voi 3 nam kinh nghiem")

    assert result.job_title == "Business Analyst"
    assert result.job_title_normalized == "business analyst"
    assert result.location == "Ha Noi"
    assert result.location_normalized == "ha noi"
    assert result.experience_years == 3
    assert result.currency == "VND"
    assert len(llm.calls) == 1


def test_llm_can_mark_salary_query_as_missing_job_title() -> None:
    service = SalaryQueryUnderstandingService(
        llm=FakeLlm(
            {
                "job_title": None,
                "location": "Ha Noi",
                "experience_years": 3,
                "currency": "VND",
                "confidence": "high",
            }
        )
    )

    result = service.extract("Toi co 3 nam kinh nghiem o Ha Noi, luong bao nhieu?")

    assert result.job_title is None
    assert result.job_title_normalized is None
    assert result.location == "Ha Noi"
    assert result.experience_years == 3


def test_falls_back_to_deterministic_normalizer_when_llm_fails() -> None:
    service = SalaryQueryUnderstandingService(llm=FakeLlm(RuntimeError("llm unavailable")))

    result = service.extract("Luong Business Analyst tai Ha Noi voi 3 nam kinh nghiem")

    assert result.job_title is not None
    assert result.job_title_normalized == "business analyst"
    assert result.experience_years == 3
