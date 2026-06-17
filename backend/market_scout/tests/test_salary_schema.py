from backend.market_scout.schemas.salary import SalaryJobRecord


def test_salary_job_record_converts_million_vnd_fields() -> None:
    record = SalaryJobRecord.from_firestore(
        "doc-1",
        {
            "job_id": "35B991C9",
            "job_url": "https://careerviet.vn/vi/tim-viec-lam/sales-executive-b2b.35B991C9.html",
            "company": "Công ty Cổ Phần Công nghiệp In & Bao Bì Khang",
            "job_title": "Sales Executive B2B",
            "min_salary": 12,
            "max_salary": 17,
            "min_experience": 2,
            "Địa điểm làm việc": ["Hồ Chí Minh"],
        },
    )

    assert record is not None
    assert record.salary_min_vnd == 12_000_000
    assert record.salary_max_vnd == 17_000_000
    assert record.currency == "VND"
    assert record.period == "monthly"
    assert record.locations == ["Hồ Chí Minh"]
    assert record.has_salary is True
