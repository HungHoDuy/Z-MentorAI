from __future__ import annotations

from collections.abc import Sequence

from backend.market_scout.repositories.trend_tracker.job_mapping_embedding_repository import JobMappingEmbeddingRepository
from backend.market_scout.schemas.trend_tracker.role_fact_match import RoleFactMatch
from backend.market_scout.services.salary_benchmark.vertex_embedding_service import EmbeddingService, VertexTextEmbeddingService
from backend.market_scout.services.trend_tracker.role_fact_search_service import DEFAULT_TOP_K


DEFAULT_SEMANTIC_FETCH_K = 20
DEFAULT_DISTANCE_THRESHOLD = None


class SemanticRoleFactSearcher:
    """Semantic role matcher backed by job_mapping_embedding Firestore vector search."""

    def __init__(
        self,
        *,
        embedding_service: EmbeddingService | None = None,
        repository: JobMappingEmbeddingRepository | None = None,
        fetch_k: int = DEFAULT_SEMANTIC_FETCH_K,
        distance_threshold: float | None = DEFAULT_DISTANCE_THRESHOLD,
        filter_location: bool = False,
    ) -> None:
        if fetch_k <= 0:
            raise ValueError("fetch_k must be positive.")
        self.embedding_service = embedding_service or VertexTextEmbeddingService(task_type="RETRIEVAL_QUERY")
        self.repository = repository or JobMappingEmbeddingRepository()
        self.fetch_k = fetch_k
        self.distance_threshold = distance_threshold
        self.filter_location = filter_location

    def search(
        self,
        *,
        role_query: str,
        location_id: str | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> Sequence[RoleFactMatch]:
        if top_k <= 0:
            raise ValueError("top_k must be positive.")
        query_text = _build_role_query_text(role_query)
        if not query_text:
            return []

        query_embedding = self.embedding_service.embed_query(query_text)
        return self.repository.search(
            query_embedding=query_embedding,
            location_id=location_id,
            top_k=top_k,
            fetch_k=max(top_k, self.fetch_k),
            distance_threshold=self.distance_threshold,
            filter_location=self.filter_location,
        )


def _build_role_query_text(role_query: str | None) -> str:
    if not role_query:
        return ""
    text = " ".join(str(role_query).split())
    if not text:
        return ""
    return f"Job title or role: {text}"