from backend.market_scout.services.salary_query_normalizer import SalaryQueryNormalizer


def test_extract_salary_query_entities() -> None:
    query = "Lương Sales Executive B2B ở Hồ Chí Minh với 2 năm kinh nghiệm là bao nhiêu?"

    extracted = SalaryQueryNormalizer().extract(query)

    assert extracted.job_title == "Sales Executive B2B"
    assert extracted.job_title_normalized == "sales executive b2b"
    assert extracted.location == "Hồ Chí Minh"
    assert extracted.location_normalized == "ho chi minh"
    assert extracted.experience_years == 2
    assert extracted.currency == "VND"


def test_normalize_location_aliases() -> None:
    normalizer = SalaryQueryNormalizer()

    assert normalizer.extract_location("lương data analyst tại TP.HCM") == "Hồ Chí Minh"
    assert normalizer.extract_location("lương backend developer ở HN") == "Hà Nội"
