from backend.market_scout.services import SalaryIndexService


def test_salary_index_service_builds_title_and_composite_search_keys() -> None:
    fields = SalaryIndexService().build_index_fields(
        "doc-1",
        {
            "job_title": "Sales Executive B2B",
            "min_salary": 12,
            "max_salary": 17,
            "Địa điểm làm việc": ["Hồ Chí Minh"],
        },
    )

    assert fields is not None
    assert fields["job_title_normalized"] == "sales executive b2b"
    assert "sales b2b" in fields["job_title_search_keys"]
    assert "sales executive b2b" in fields["job_title_search_keys"]
    assert "ho chi minh" in fields["location_normalized"]
    assert "sales b2b|ho chi minh" in fields["salary_search_keys"]
    assert fields["salary_min_vnd"] == 12_000_000
    assert fields["salary_max_vnd"] == 17_000_000
