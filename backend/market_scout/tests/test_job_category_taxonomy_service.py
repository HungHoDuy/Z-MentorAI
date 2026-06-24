from backend.market_scout.services.trend_tracker.job_category_taxonomy_service import (
    DEFAULT_JOB_CATEGORIES,
    JobCategoryTaxonomyService,
)


def test_seed_taxonomy_contains_the_70_valid_observed_categories() -> None:
    assert len(DEFAULT_JOB_CATEGORIES) == 70


def test_classifies_multiple_categories_and_keeps_their_broad_families() -> None:
    service = JobCategoryTaxonomyService()

    match = service.classify(
        ["Quản lý chất lượng (QA/QC)", "Thực phẩm & Đồ uống"]
    )

    assert match.job_category_ids == ["quality_assurance", "food_beverage"]
    assert match.job_family_ids == ["operations", "people_services"]
    assert match.unmatched_labels == []
    assert match.invalid_labels == []


def test_keeps_invalid_and_unmatched_labels_out_of_taxonomy_dimensions() -> None:
    service = JobCategoryTaxonomyService()
    raw_labels = service.extract_raw_labels(
        {
            "Ngành nghề": "CNTT - Phần mềm, Tỉnh, Nhãn chưa định nghĩa",
        }
    )

    match = service.classify(raw_labels)

    assert match.job_category_ids == ["software_it"]
    assert match.job_family_ids == ["digital_telecom"]
    assert match.invalid_labels == ["Tỉnh"]
    assert match.unmatched_labels == ["Nhãn chưa định nghĩa"]
