from __future__ import annotations

from backend.market_scout.schemas.trend_tracker.role_fact_match import RoleFactMatch
from backend.market_scout.services.trend_tracker.semantic_role_fact_searcher import SemanticRoleFactSearcher


class FakeEmbeddingService:
    model_name = "fake"

    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1, 0.2, 0.3]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return []


class FakeRepository:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return [
            RoleFactMatch(
                job_key="backend-1",
                job_title="Backend Developer",
                job_category_ids=["software_it"],
                job_family_ids=["digital_telecom"],
                location_ids=["ha-noi"],
                score=0.88,
                match_method="semantic",
            )
        ]


def test_semantic_role_fact_searcher_embeds_query_and_calls_repository() -> None:
    embedding_service = FakeEmbeddingService()
    repository = FakeRepository()
    searcher = SemanticRoleFactSearcher(
        embedding_service=embedding_service,
        repository=repository,
        fetch_k=20,
        filter_location=True,
    )

    matches = searcher.search(role_query="backend engineer", location_id="ha-noi", top_k=5)

    assert embedding_service.queries == ["Job title or role: backend engineer"]
    assert len(matches) == 1
    assert matches[0].match_method == "semantic"
    assert repository.calls == [
        {
            "query_embedding": [0.1, 0.2, 0.3],
            "location_id": "ha-noi",
            "top_k": 5,
            "fetch_k": 20,
            "distance_threshold": None,
            "filter_location": True,
        }
    ]


def test_semantic_role_fact_searcher_allows_fetch_k_override() -> None:
    embedding_service = FakeEmbeddingService()
    repository = FakeRepository()
    searcher = SemanticRoleFactSearcher(
        embedding_service=embedding_service,
        repository=repository,
        fetch_k=20,
    )

    searcher.search(role_query="backend engineer", location_id="ha-noi", top_k=100, fetch_k=200)

    assert repository.calls[0]["top_k"] == 100
    assert repository.calls[0]["fetch_k"] == 200
