from __future__ import annotations

from typing import Any, Mapping

from backend.market_scout.repositories.salary_benchmark.salary_repository import (
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.pipelines.trend_tracker.embed_job_mapping_pipeline import (
    DEFAULT_EMBEDDING_FIELD,
    DEFAULT_JOB_MAPPING_EMBEDDING_COLLECTION,
)
from backend.market_scout.schemas.trend_tracker.role_fact_match import RoleFactMatch


DEFAULT_DISTANCE_FIELD = "vector_distance"
LOCATION_SCORE_BOOST = 0.1


class JobMappingEmbeddingRepository:
    """Firestore vector reads for role/category mapping over job_mapping_embedding."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        embedding_collection: str | None = None,
        embedding_field: str | None = None,
        distance_field: str | None = None,
        stream_timeout: int = 60,
    ) -> None:
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.embedding_collection = embedding_collection or env_or_default(
            "MARKET_SCOUT_JOB_MAPPING_EMBEDDING_COLLECTION",
            DEFAULT_JOB_MAPPING_EMBEDDING_COLLECTION,
        )
        self.embedding_field = embedding_field or env_or_default(
            "MARKET_SCOUT_JOB_MAPPING_EMBEDDING_FIELD",
            DEFAULT_EMBEDDING_FIELD,
        )
        self.distance_field = distance_field or env_or_default(
            "MARKET_SCOUT_JOB_MAPPING_DISTANCE_FIELD",
            DEFAULT_DISTANCE_FIELD,
        )
        self.stream_timeout = stream_timeout

    def search(
        self,
        *,
        query_embedding: list[float],
        location_id: str | None = None,
        top_k: int = 5,
        fetch_k: int | None = None,
        distance_threshold: float | None = None,
        filter_location: bool = False,
    ) -> list[RoleFactMatch]:
        if not query_embedding:
            return []
        if top_k <= 0:
            raise ValueError("top_k must be positive.")
        if fetch_k is not None and fetch_k <= 0:
            raise ValueError("fetch_k must be positive when provided.")

        vector_query = self._build_vector_query(
            query_embedding,
            limit=fetch_k or top_k,
            distance_threshold=distance_threshold,
        )
        matches: list[RoleFactMatch] = []
        for snapshot in vector_query.stream(timeout=self.stream_timeout):
            match = role_fact_match_from_mapping_document(
                snapshot.id,
                snapshot.to_dict() or {},
                distance_field=self.distance_field,
                location_id=location_id,
                filter_location=filter_location,
            )
            if match is None:
                continue
            matches.append(match)

        return sorted(matches, key=lambda item: (-item.score, item.job_title, item.job_key))[:top_k]

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

        return self.firestore_client.collection(self.embedding_collection).find_nearest(
            vector_field=self.embedding_field,
            query_vector=Vector(query_embedding),
            limit=limit,
            distance_measure=DistanceMeasure.COSINE,
            distance_result_field=self.distance_field,
            distance_threshold=distance_threshold,
        )


def role_fact_match_from_mapping_document(
    document_id: str,
    data: Mapping[str, Any],
    *,
    distance_field: str = DEFAULT_DISTANCE_FIELD,
    location_id: str | None = None,
    filter_location: bool = False,
) -> RoleFactMatch | None:
    job_title = _optional_text(data.get("job_title"))
    if not job_title:
        return None

    location_ids = _string_list(data.get("location_ids"))
    if filter_location and location_id and location_id not in location_ids:
        return None

    job_category_ids = _string_list(data.get("job_category_ids"))
    job_family_ids = _string_list(data.get("job_family_ids"))
    if not job_category_ids or not job_family_ids:
        return None

    distance = _to_float(data.get(distance_field))
    score = _score_from_distance(distance)
    if location_id and location_id in location_ids:
        score = min(score + LOCATION_SCORE_BOOST, 1.0)

    return RoleFactMatch(
        job_key=_optional_text(data.get("job_key")) or document_id,
        job_title=job_title,
        company=_optional_text(data.get("company")),
        job_url=_optional_text(data.get("job_url")),
        job_category_ids=job_category_ids,
        job_family_ids=job_family_ids,
        location_ids=location_ids,
        is_active=_to_bool(data.get("is_active")),
        score=score,
        match_method="semantic",
    )


def _score_from_distance(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - distance))


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[str] = []
    seen: set[str] = set()
    for item in values:
        text = _optional_text(item)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def _to_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    text = str(value).strip().casefold()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None
