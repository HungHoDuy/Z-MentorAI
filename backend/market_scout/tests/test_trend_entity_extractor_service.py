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


def test_maps_structured_job_category_hint_to_category_and_family() -> None:
    extractor = TrendEntityExtractorService()

    entities = extractor.extract(
        "nhu cau tuyen dung tai Ha Noi co cao khong?",
        {"job_category_hint": "banking"},
    )

    assert entities == {
        "job_category_id": "banking",
        "job_family_id": "finance_legal",
        "location_id": "ha-noi",
    }

def test_maps_structured_job_family_hint_directly() -> None:
    extractor = TrendEntityExtractorService()

    entities = extractor.extract(
        "nhu cau tuyen dung tai Ha Noi co cao khong?",
        {"job_family_hint": "commercial"},
    )

    assert entities == {
        "job_family_id": "commercial",
        "location_id": "ha-noi",
    }


class FakeRoleSearchService:
    def __init__(self) -> None:
        self.calls = []

    def resolve_role(self, *, role_query: str, location_id: str | None = None, top_k: int = 5):
        self.calls.append({"role_query": role_query, "location_id": location_id, "top_k": top_k})
        return FakeRoleResolutionResult(accepted=True)


class FakeRoleResolutionResult:
    def __init__(self, *, accepted: bool) -> None:
        self.accepted = accepted
        self.resolved_job_category_id = "software_it" if accepted else None
        self.resolved_job_family_id = "digital_telecom" if accepted else None
        self.confidence = "medium" if accepted else "low"
        self.rejection_reason = None if accepted else "weak_match_score"
        self.matches = [FakeRoleMatch()] if accepted else []


class FakeRejectingRoleSearchService:
    def resolve_role(self, *, role_query: str, location_id: str | None = None, top_k: int = 5):
        return FakeRoleResolutionResult(accepted=False)


class FakeRoleMatch:
    match_method = "keyword"


def test_maps_role_mention_by_searching_trend_job_facts() -> None:
    role_search_service = FakeRoleSearchService()
    extractor = TrendEntityExtractorService(role_search_service=role_search_service)

    entities = extractor.extract(
        "backend engineer tai Ha Noi co dang tuyen nhieu khong?",
        {
            "role_mention": "backend engineer",
            "location_text": "Ha Noi",
            "job_category_hint": None,
            "job_family_hint": None,
        },
    )

    assert entities == {
        "location_id": "ha-noi",
        "resolved_job_category_id": "software_it",
        "job_category_id": "software_it",
        "resolved_job_family_id": "digital_telecom",
        "job_family_id": "digital_telecom",
        "role_resolution_confidence": "medium",
        "role_match_method": "keyword",
    }
    assert role_search_service.calls == [
        {"role_query": "backend engineer", "location_id": "ha-noi", "top_k": 5}
    ]

def test_rejected_role_resolution_does_not_force_category_or_family() -> None:
    extractor = TrendEntityExtractorService(role_search_service=FakeRejectingRoleSearchService())

    entities = extractor.extract(
        "unknown role tai Ha Noi co dang tuyen nhieu khong?",
        {"role_mention": "unknown role", "location_text": "Ha Noi"},
    )

    assert entities == {
        "location_id": "ha-noi",
        "role_resolution_status": "rejected",
        "role_resolution_reason": "weak_match_score",
    }