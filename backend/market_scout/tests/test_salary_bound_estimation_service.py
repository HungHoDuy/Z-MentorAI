from backend.market_scout.services import SalaryBoundEstimationService


def test_salary_bound_estimation_uses_median_factor_for_open_ranges() -> None:
    service = SalaryBoundEstimationService()
    documents = [
        ("range-1", {"job_title": "Sales", "salary_min_vnd": 10_000_000, "salary_max_vnd": 15_000_000}),
        ("range-2", {"job_title": "Sales", "salary_min_vnd": 20_000_000, "salary_max_vnd": 30_000_000}),
        ("range-3", {"job_title": "Sales", "salary_min_vnd": 12_000_000, "salary_max_vnd": 18_000_000}),
    ]

    factor = service.calculate_factor(documents)

    assert factor == 1.5

    lower_bound = service.estimate(
        "lower",
        {"job_title": "Sales", "salary_min_vnd": 12_000_000, "salary_max_vnd": 0},
        factor,
    )
    upper_bound = service.estimate(
        "upper",
        {"job_title": "Sales", "salary_min_vnd": 0, "salary_max_vnd": 30_000_000},
        factor,
    )

    assert lower_bound is not None
    assert lower_bound.salary_min_vnd == 12_000_000
    assert lower_bound.salary_max_vnd == 18_000_000
    assert lower_bound.min_salary == 12
    assert lower_bound.max_salary == 18
    assert lower_bound.salary_factor == 1.5

    assert upper_bound is not None
    assert upper_bound.salary_min_vnd == 20_000_000
    assert upper_bound.salary_max_vnd == 30_000_000
    assert upper_bound.min_salary == 20
    assert upper_bound.max_salary == 30
    assert upper_bound.salary_factor == 1.5


def test_salary_bound_estimation_ignores_outlier_factors() -> None:
    service = SalaryBoundEstimationService()
    documents = [
        ("range-1", {"job_title": "Sales", "salary_min_vnd": 10_000_000, "salary_max_vnd": 15_000_000}),
        ("range-2", {"job_title": "Sales", "salary_min_vnd": 10_000_000, "salary_max_vnd": 200_000_000}),
    ]

    assert service.calculate_factor(documents) == 1.5


def test_salary_bound_estimation_treats_none_as_missing_bound() -> None:
    service = SalaryBoundEstimationService()

    lower_bound = service.estimate(
        "lower",
        {"job_title": "Sales", "salary_min_vnd": 12_000_000, "salary_max_vnd": None},
        1.5,
    )
    upper_bound = service.estimate(
        "upper",
        {"job_title": "Sales", "salary_min_vnd": None, "salary_max_vnd": 30_000_000},
        1.5,
    )

    assert lower_bound is not None
    assert lower_bound.salary_min_vnd == 12_000_000
    assert lower_bound.salary_max_vnd == 18_000_000

    assert upper_bound is not None
    assert upper_bound.salary_min_vnd == 20_000_000
    assert upper_bound.salary_max_vnd == 30_000_000


def test_salary_bound_estimation_treats_repeated_global_max_as_missing_upper_bound() -> None:
    service = SalaryBoundEstimationService(min_sentinel_count=2)
    documents = [
        ("range-1", {"job_title": "Sales", "salary_min_vnd": 10_000_000, "salary_max_vnd": 15_000_000}),
        ("lower-1", {"job_title": "Sales", "salary_min_vnd": 12_000_000, "salary_max_vnd": 300_000_000}),
        ("lower-2", {"job_title": "Sales", "salary_min_vnd": 14_000_000, "salary_max_vnd": 300_000_000}),
    ]

    sentinel = service.detect_max_salary_sentinel(documents)
    factor = service.calculate_factor(documents, max_salary_sentinel_vnd=sentinel)
    estimate = service.estimate(
        "lower-1",
        {"job_title": "Sales", "salary_min_vnd": 12_000_000, "salary_max_vnd": 300_000_000},
        factor,
        max_salary_sentinel_vnd=sentinel,
    )

    assert sentinel == 300_000_000
    assert factor == 1.5
    assert estimate is not None
    assert estimate.salary_min_vnd == 12_000_000
    assert estimate.salary_max_vnd == 18_000_000
