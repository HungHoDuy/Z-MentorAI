from datetime import date

from backend.market_scout.services.trend_tracker.job_category_trend_job_fact_normalizer import (
    JobCategoryTrendJobFactNormalizer,
)


def test_normalizes_job_categories_without_emitting_role_or_skill_dimensions() -> None:
    fact = JobCategoryTrendJobFactNormalizer().normalize(
        "raw-1",
        {
            "job_id": "35C19E7E",
            "job_title": "Nhân Viên QA",
            "company": "Example Foods",
            "Địa điểm làm việc": ["Hồ Chí Minh"],
            "Ngành nghề": "Quản lý chất lượng (QA/QC), Thực phẩm & Đồ uống",
            "Ngày cập nhật": "23/05/2026",
            "Hết hạn nộp": "21/06/2026",
            "Yêu Cầu Công Việc": "Có HACCP và Excel.",
            "Mô tả Công việc": "Kiểm soát chất lượng sản phẩm.",
        },
        observed_at=date(2026, 6, 20),
    )

    assert fact is not None
    assert fact.job_category_ids == ["quality_assurance", "food_beverage"]
    assert fact.job_family_ids == ["operations", "people_services"]
    assert fact.location_ids == ["ho-chi-minh"]
    assert fact.source_updated_at == date(2026, 5, 23)
    assert fact.source_expires_at == date(2026, 6, 21)
    assert fact.is_active is True

    document = fact.to_dict()
    assert document["raw_job_category_labels"] == [
        "Quản lý chất lượng (QA/QC)",
        "Thực phẩm & Đồ uống",
    ]
    assert "role_id" not in document
    assert "skill_ids" not in document
    assert "industry_ids" not in document
