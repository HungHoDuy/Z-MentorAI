from backend.market_scout.services import JobEmbeddingTextService


def test_job_embedding_text_service_builds_salary_job_text() -> None:
    text = JobEmbeddingTextService().build_text(
        "doc-1",
        {
            "company": "ABC",
            "job_title": "Sales Executive B2B",
            "min_salary": 12,
            "max_salary": 17,
            "min_experience": 2,
            "Địa điểm làm việc": ["Hồ Chí Minh"],
            "Yêu Cầu Công Việc": "Có kinh nghiệm Sales B2B.",
            "Thông tin khác": "Lương: 12 Tr - 17 Tr VND",
        },
    )

    assert text is not None
    assert "Job title: Sales Executive B2B" in text
    assert "Location: Hồ Chí Minh" in text
    assert "Salary: 12 - 17 million VND per month" in text
    assert "Requirements: Có kinh nghiệm Sales B2B." in text
