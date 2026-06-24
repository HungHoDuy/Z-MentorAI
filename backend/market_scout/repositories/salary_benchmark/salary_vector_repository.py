from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.market_scout.repositories.salary_benchmark.salary_repository import (
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.schemas.salary_benchmark.salary import SalaryJobRecord, SalarySearchQuery
from backend.market_scout.services.salary_benchmark.salary_query_normalizer import SalaryQueryNormalizer
from backend.market_scout.services.salary_benchmark.vertex_embedding_service import EmbeddingService, VertexTextEmbeddingService


DEFAULT_VECTOR_COLLECTION = "data_vector_embeddings"
DEFAULT_EMBEDDING_FIELD = "embedding"
DEFAULT_DISTANCE_FIELD = "vector_distance"


@dataclass(frozen=True)
class SalaryVectorSearchResult:
    record: SalaryJobRecord
    distance: float | None
    embedding_text: str | None
    raw_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "record": self.record.to_dict(),
            "distance": self.distance,
            "embedding_text": self.embedding_text,
        }


class SalaryVectorRepository:
    """Vector search repository for salary benchmark job retrieval."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        embedding_service: EmbeddingService | None = None,
        normalizer: SalaryQueryNormalizer | None = None,
        vector_collection: str | None = None,
        vector_field: str | None = None,
        distance_field: str | None = None,
        stream_timeout: int = 60,
    ) -> None:
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.embedding_service = embedding_service or VertexTextEmbeddingService(task_type="RETRIEVAL_QUERY")
        self.normalizer = normalizer or SalaryQueryNormalizer()
        self.vector_collection = vector_collection or env_or_default(
            "MARKET_SCOUT_VECTOR_COLLECTION",
            DEFAULT_VECTOR_COLLECTION,
        )
        self.vector_field = vector_field or env_or_default("MARKET_SCOUT_VECTOR_FIELD", DEFAULT_EMBEDDING_FIELD)
        self.distance_field = distance_field or env_or_default(
            "MARKET_SCOUT_VECTOR_DISTANCE_FIELD",
            DEFAULT_DISTANCE_FIELD,
        )
        self.stream_timeout = stream_timeout

    def search(
        self,
        query: SalarySearchQuery | str,
        *,
        top_k: int = 20,
        fetch_k: int | None = None,
        require_salary: bool = True,
        filter_location: bool = True,
        filter_experience: bool = True,
        distance_threshold: float | None = None,
    ) -> list[SalaryVectorSearchResult]:
        search_query = self.normalizer.extract(query) if isinstance(query, str) else query
        query_embedding = self.embedding_service.embed_query(self._build_query_text(search_query))
        vector_query = self._build_vector_query(
            query_embedding,
            limit=fetch_k or top_k,
            distance_threshold=distance_threshold,
        )

        results: list[SalaryVectorSearchResult] = []
        for snapshot in vector_query.stream(timeout=self.stream_timeout):
            data = snapshot.to_dict() or {}
            record = SalaryJobRecord.from_firestore(snapshot.id, data)
            if record is None:
                continue
            if require_salary and not record.has_salary:
                continue
            if filter_location and not self.normalizer.location_matches(record.locations, search_query.location):
                continue
            if filter_experience and not self._experience_matches(record, search_query):
                continue

            results.append(
                SalaryVectorSearchResult(
                    record=record,
                    distance=_to_float(data.get(self.distance_field)),
                    embedding_text=data.get("embedding_text"),
                    raw_data=data,
                )
            )
            if len(results) >= top_k:
                break

        return results

    def search_records(self, query: SalarySearchQuery | str, *, top_k: int = 20) -> list[SalaryJobRecord]:
        return [result.record for result in self.search(query, top_k=top_k)]

    def _build_vector_query(
        self,
        query_embedding: list[float],
        *,
        limit: int,
        distance_threshold: float | None,
    ) -> Any:
        try:
            from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
            from google.cloud.firestore_v1.vector import Vector
        except ImportError as exc:
            raise RuntimeError(
                "Missing Firestore vector search support. Upgrade google-cloud-firestore in requirements.txt."
            ) from exc

        return self.firestore_client.collection(self.vector_collection).find_nearest(
            vector_field=self.vector_field,
            query_vector=Vector(query_embedding),
            limit=limit,
            distance_measure=DistanceMeasure.COSINE,
            distance_result_field=self.distance_field,
            distance_threshold=distance_threshold,
        )

    @staticmethod
    def _build_query_text(query: SalarySearchQuery) -> str:
        parts = [query.raw_query]
        if query.job_title:
            parts.append(f"Job title: {query.job_title}")
        if query.location:
            parts.append(f"Location: {query.location}")
        if query.experience_years is not None:
            parts.append(f"Experience: {query.experience_years} years")
        return "\n".join(parts)

    @staticmethod
    def _experience_matches(record: SalaryJobRecord, query: SalarySearchQuery) -> bool:
        if query.experience_years is None or record.min_experience is None:
            return True
        return record.min_experience <= query.experience_years


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
