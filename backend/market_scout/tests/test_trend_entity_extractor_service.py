from backend.market_scout.services.trend_tracker.trend_entity_extractor_service import TrendEntityExtractorService


def test_extracts_job_family_and_location_from_query() -> None:
    extractor = TrendEntityExtractorService()

    entities = extractor.extract("nhu cau tuyen dung vi tri commercial tai Ha Noi co cao khong?")

    assert entities == {
        "job_family_id": "commercial",
        "location_id": "ha-noi",
    }


def test_extracts_job_category_and_location_from_query() -> None:
    extractor = TrendEntityExtractorService()

    entities = extractor.extract("nhu cau tuyen dung nganh banking tai Ha Noi co cao khong?")

    assert entities == {
        "job_category_id": "banking",
        "location_id": "ha-noi",
    }


def test_does_not_override_existing_structured_entities() -> None:
    extractor = TrendEntityExtractorService()

    entities = extractor.extract(
        "nhu cau tuyen dung banking tai Ha Noi co cao khong?",
        {"job_category_id": "software_it", "location_id": "ho-chi-minh"},
    )

    assert entities == {}

