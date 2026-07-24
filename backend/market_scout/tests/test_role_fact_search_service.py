from __future__ import annotations

from backend.market_scout.schemas.trend_tracker.job_category_trend import JobCategoryTrendJobFact
from backend.market_scout.schemas.trend_tracker.role_fact_match import RoleFactMatch
from backend.market_scout.services.trend_tracker.role_fact_search_service import RoleFactSearchService




class FakeSemanticSearcher:
    def search(self, *, role_query: str, location_id: str | None = None, top_k: int = 5):
        return [
            RoleFactMatch(
                job_key="backend-hn",
                job_title="Backend Developer",
                job_category_ids=["software_it"],
                job_family_ids=["digital_telecom"],
                location_ids=["ha-noi"],
                score=0.9,
                match_method="semantic",
            )
        ]

class FakeFactRepository:
    def __init__(self, facts: list[JobCategoryTrendJobFact]) -> None:
        self.facts = facts
        self.calls: list[dict[str, object]] = []

    def list_for_role_search(self, *, location_id: str | None = None, max_scan: int = 2000):
        self.calls.append({"location_id": location_id, "max_scan": max_scan})
        if location_id:
            return [fact for fact in self.facts if location_id in fact.location_ids]
        return list(self.facts)


def test_search_scores_title_overlap_and_location() -> None:
    repository = FakeFactRepository(
        [
            _fact(
                job_key="backend-hn",
                job_title="Backend Developer",
                job_category_ids=["software_it"],
                job_family_ids=["digital_telecom"],
                location_ids=["ha-noi"],
            ),
            _fact(
                job_key="sales-hn",
                job_title="Sales Executive",
                job_category_ids=["sales_business"],
                job_family_ids=["commercial"],
                location_ids=["ha-noi"],
            ),
        ]
    )
    service = RoleFactSearchService(fact_repository=repository)

    matches = service.search(role_query="backend engineer", location_id="ha-noi", top_k=5)

    assert [match.job_key for match in matches] == ["backend-hn"]
    assert matches[0].job_category_ids == ["software_it"]
    assert matches[0].job_family_ids == ["digital_telecom"]
    assert matches[0].match_method == "keyword"
    assert repository.calls == [{"location_id": "ha-noi", "max_scan": 2000}]


def test_resolve_category_and_family_from_top_matches() -> None:
    repository = FakeFactRepository(
        [
            _fact(
                job_key="banking-1",
                job_title="Chuyen vien quan he khach hang",
                job_category_ids=["banking"],
                job_family_ids=["finance_legal"],
                location_ids=["ho-chi-minh"],
            ),
            _fact(
                job_key="banking-2",
                job_title="Quan he khach hang doanh nghiep",
                job_category_ids=["banking"],
                job_family_ids=["finance_legal"],
                location_ids=["ho-chi-minh"],
            ),
        ]
    )
    service = RoleFactSearchService(fact_repository=repository)

    category_id, family_id, matches = service.resolve_category_and_family(
        role_query="chuyen vien quan he khach hang",
        location_id="ho-chi-minh",
        top_k=5,
    )

    assert category_id == "banking"
    assert family_id == "finance_legal"
    assert len(matches) == 2


def _fact(
    *,
    job_key: str,
    job_title: str,
    job_category_ids: list[str],
    job_family_ids: list[str],
    location_ids: list[str],
    is_active: bool = True,
) -> JobCategoryTrendJobFact:
    return JobCategoryTrendJobFact(
        job_key=job_key,
        source="test",
        source_job_id=None,
        job_url=None,
        canonical_job_url=None,
        job_title=job_title,
        company=None,
        company_key=None,
        location_ids=location_ids,
        seniority=None,
        employment_type=None,
        source_updated_at=None,
        source_expires_at=None,
        is_active=is_active,
        content_hash="hash",
        requirements_text=None,
        description_text=None,
        raw_job_category_labels=[],
        job_category_ids=job_category_ids,
        job_family_ids=job_family_ids,
        unmatched_job_category_labels=[],
        invalid_job_category_labels=[],
        taxonomy_version="test",
    )

def test_search_marks_duplicate_keyword_and_semantic_match_as_hybrid() -> None:
    repository = FakeFactRepository(
        [
            _fact(
                job_key="backend-hn",
                job_title="Backend Developer",
                job_category_ids=["software_it"],
                job_family_ids=["digital_telecom"],
                location_ids=["ha-noi"],
            ),
        ]
    )
    service = RoleFactSearchService(
        fact_repository=repository,
        semantic_searcher=FakeSemanticSearcher(),
    )

    matches = service.search(role_query="backend engineer", location_id="ha-noi", top_k=5)

    assert len(matches) == 1
    assert matches[0].job_key == "backend-hn"
    assert matches[0].match_method == "hybrid"
    assert matches[0].score == 0.9

class StaticSemanticSearcher:
    def __init__(self, matches: list[RoleFactMatch]) -> None:
        self.matches = matches

    def search(self, *, role_query: str, location_id: str | None = None, top_k: int = 5):
        return self.matches[:top_k]



class RecordingSemanticSearcher:
    def __init__(self, matches: list[RoleFactMatch]) -> None:
        self.matches = matches
        self.calls: list[dict[str, object]] = []

    def search(
        self,
        *,
        role_query: str,
        location_id: str | None = None,
        top_k: int = 5,
        fetch_k: int | None = None,
    ):
        self.calls.append(
            {
                "role_query": role_query,
                "location_id": location_id,
                "top_k": top_k,
                "fetch_k": fetch_k,
            }
        )
        return self.matches[:top_k]


def test_search_for_demand_uses_wider_defaults_without_changing_mapping_search() -> None:
    semantic_searcher = RecordingSemanticSearcher(
        [
            _match(
                f"backend-{index}",
                f"Backend Developer {index}",
                "software_it",
                "digital_telecom",
                ["ha-noi"],
                0.9 - (index * 0.001),
            )
            for index in range(120)
        ]
    )
    service = RoleFactSearchService(
        fact_repository=FakeFactRepository([]),
        semantic_searcher=semantic_searcher,
    )

    mapping_matches = service.search(role_query="backend engineer", location_id="ha-noi")
    demand_matches = service.search_for_demand(role_query="backend engineer", location_id="ha-noi")

    assert len(mapping_matches) == 5
    assert len(demand_matches) == 100
    assert semantic_searcher.calls == [
        {
            "role_query": "backend engineer",
            "location_id": "ha-noi",
            "top_k": 5,
            "fetch_k": None,
        },
        {
            "role_query": "backend engineer",
            "location_id": "ha-noi",
            "top_k": 100,
            "fetch_k": 200,
        },
    ]

def test_resolve_role_accepts_clear_multi_match_category() -> None:
    service = RoleFactSearchService(
        fact_repository=FakeFactRepository([]),
        semantic_searcher=StaticSemanticSearcher(
            [
                _match("ba-1", "Business Analyst", "software_it", "digital_telecom", ["ha-noi"], 0.82),
                _match("ba-2", "IT Business Analyst", "software_it", "digital_telecom", ["ha-noi"], 0.74),
                _match("ba-3", "Business Analyst ERP", "software_it", "digital_telecom", ["ho-chi-minh"], 0.66),
            ]
        ),
    )

    resolution = service.resolve_role(role_query="business analyst", location_id="ha-noi", top_k=5)

    assert resolution.accepted is True
    assert resolution.resolved_job_category_id == "software_it"
    assert resolution.resolved_job_family_id == "digital_telecom"
    assert resolution.confidence == "medium"
    assert resolution.top_score == 0.82
    assert resolution.matched_fact_count == 3
    assert round(resolution.category_score_share, 4) == 1.0
    assert round(resolution.location_match_share or 0, 4) == 0.6667


def test_resolve_role_accepts_single_very_strong_match() -> None:
    service = RoleFactSearchService(
        fact_repository=FakeFactRepository([]),
        semantic_searcher=StaticSemanticSearcher(
            [_match("ba-1", "Business Analyst", "software_it", "digital_telecom", ["ha-noi"], 0.9)]
        ),
    )

    resolution = service.resolve_role(role_query="business analyst", location_id="ha-noi", top_k=5)

    assert resolution.accepted is True
    assert resolution.confidence == "medium"
    assert resolution.resolved_job_category_id == "software_it"


def test_resolve_role_rejects_single_weak_match() -> None:
    service = RoleFactSearchService(
        fact_repository=FakeFactRepository([]),
        semantic_searcher=StaticSemanticSearcher(
            [_match("ba-1", "Business Analyst", "software_it", "digital_telecom", ["ha-noi"], 0.7)]
        ),
    )

    resolution = service.resolve_role(role_query="business analyst", location_id="ha-noi", top_k=5)

    assert resolution.accepted is False
    assert resolution.rejection_reason == "insufficient_sample"
    assert resolution.resolved_job_category_id is None


def test_resolve_role_rejects_weak_location_coverage() -> None:
    service = RoleFactSearchService(
        fact_repository=FakeFactRepository([]),
        semantic_searcher=StaticSemanticSearcher(
            [
                _match("ba-1", "Business Analyst", "software_it", "digital_telecom", ["da-nang"], 0.9),
                _match("ba-2", "IT Business Analyst", "software_it", "digital_telecom", ["ho-chi-minh"], 0.8),
                _match("ba-3", "Business Analyst ERP", "software_it", "digital_telecom", ["ha-noi"], 0.75),
            ]
        ),
    )

    resolution = service.resolve_role(role_query="business analyst", location_id="ha-noi", top_k=5)

    assert resolution.accepted is False
    assert resolution.rejection_reason == "weak_location_coverage"
    assert round(resolution.location_match_share or 0, 4) == 0.3333


def test_resolve_role_rejects_ambiguous_category() -> None:
    service = RoleFactSearchService(
        fact_repository=FakeFactRepository([]),
        semantic_searcher=StaticSemanticSearcher(
            [
                _match("r-1", "Consultant", "consulting", "business_support", ["ha-noi"], 0.8),
                _match("r-2", "Consultant", "banking", "finance_legal", ["ha-noi"], 0.78),
            ]
        ),
        min_accept_category_share=0.7,
    )

    resolution = service.resolve_role(role_query="consultant", location_id="ha-noi", top_k=5)

    assert resolution.accepted is False
    assert resolution.rejection_reason == "ambiguous_category"


def _match(
    job_key: str,
    job_title: str,
    job_category_id: str,
    job_family_id: str,
    location_ids: list[str],
    score: float,
) -> RoleFactMatch:
    return RoleFactMatch(
        job_key=job_key,
        job_title=job_title,
        job_category_ids=[job_category_id],
        job_family_ids=[job_family_id],
        location_ids=location_ids,
        score=score,
        match_method="semantic",
    )