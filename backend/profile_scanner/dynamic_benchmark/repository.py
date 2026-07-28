from __future__ import annotations

import datetime
from functools import lru_cache
from typing import Any

from google.cloud import firestore

from core.config import settings
from dynamic_benchmark.schemas import DynamicBenchmarkSnapshot, MarketJobEvidence


@lru_cache(maxsize=1)
def get_firestore_client():
    return firestore.Client(
        project=settings.google_cloud_project,
        database=settings.firestore_database or "(default)",
    )


@lru_cache(maxsize=1)
def get_embedding_client():
    from google import genai
    from google.genai.types import HttpOptions

    return genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.benchmark_embedding_location,
        http_options=HttpOptions(api_version="v1"),
    )


def embed_role_query(role_query: str) -> list[float]:
    from google.genai.types import EmbedContentConfig

    response = get_embedding_client().models.embed_content(
        model=settings.benchmark_embedding_model,
        contents=[role_query],
        config=EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=settings.benchmark_embedding_dimension,
        ),
    )
    if not response.embeddings:
        return []
    return list(response.embeddings[0].values or [])


class DynamicBenchmarkRepository:
    def __init__(self, firestore_client: Any | None = None) -> None:
        self.db = firestore_client or get_firestore_client()

    def get_cached(self, cache_key: str, now: datetime.datetime) -> DynamicBenchmarkSnapshot | None:
        cache = self.db.collection(settings.benchmark_cache_collection).document(cache_key).get()
        if not cache.exists:
            return None
        cache_data = cache.to_dict() or {}
        expires_at = _to_datetime(cache_data.get("expires_at"))
        benchmark_id = str(cache_data.get("benchmark_id") or "")
        if not benchmark_id or not expires_at or expires_at <= now:
            return None
        snapshot = self.db.collection(settings.benchmark_snapshots_collection).document(benchmark_id).get()
        if not snapshot.exists:
            return None
        return DynamicBenchmarkSnapshot(**(snapshot.to_dict() or {}))

    def save(self, snapshot: DynamicBenchmarkSnapshot) -> None:
        batch = self.db.batch()
        snapshot_ref = self.db.collection(settings.benchmark_snapshots_collection).document(snapshot.benchmark_id)
        cache_ref = self.db.collection(settings.benchmark_cache_collection).document(snapshot.cache_key)
        batch.create(snapshot_ref, snapshot.as_firestore_payload())
        batch.set(
            cache_ref,
            {
                "benchmark_id": snapshot.benchmark_id,
                "role_query": snapshot.role_query,
                "level": snapshot.level,
                "location_id": snapshot.location_id,
                "compiler_version": snapshot.compiler_version,
                "expires_at": snapshot.expires_at,
                "updated_at": snapshot.generated_at,
            },
        )
        batch.commit()

    def search_market_jobs(
        self,
        *,
        role_query: str,
        location_id: str,
        level: str,
        now: datetime.datetime,
        window_days: int,
        limit: int,
    ) -> list[MarketJobEvidence]:
        from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
        from google.cloud.firestore_v1.vector import Vector

        query_vector = embed_role_query(role_query)
        if not query_vector:
            return []
        vector_query = self.db.collection(settings.benchmark_embedding_collection).find_nearest(
            vector_field=settings.benchmark_embedding_field,
            query_vector=Vector(query_vector),
            limit=limit,
            distance_measure=DistanceMeasure.COSINE,
            distance_result_field="vector_distance",
            distance_threshold=settings.benchmark_max_vector_distance,
        )
        matches = list(vector_query.stream())
        if not matches:
            return []

        distances = {
            document.id: float((document.to_dict() or {}).get("vector_distance", 1.0))
            for document in matches
        }
        references = [
            self.db.collection(settings.benchmark_job_facts_collection).document(document.id)
            for document in matches
        ]
        cutoff = (now - datetime.timedelta(days=window_days)).date()
        results = []
        for document in self.db.get_all(references):
            if not document.exists:
                continue
            data = document.to_dict() or {}
            updated_at = _to_date(data.get("source_updated_at"))
            if data.get("is_active") is False or not updated_at or updated_at < cutoff:
                continue
            locations = _string_list(data.get("location_ids"))
            if location_id not in {"", "vietnam", "all"} and location_id not in locations:
                continue
            title = _text(data.get("job_title"))
            seniority = _text(data.get("seniority"))
            if not _matches_level(title, seniority, level):
                continue
            distance = distances.get(document.id, 1.0)
            results.append(
                MarketJobEvidence(
                    job_key=_text(data.get("job_key")) or document.id,
                    job_title=title,
                    company=_text(data.get("company")),
                    job_url=_text(data.get("job_url")),
                    source=_text(data.get("source")) or "unknown",
                    source_updated_at=updated_at.isoformat(),
                    seniority=seniority,
                    location_ids=locations,
                    requirements_text=_text(data.get("requirements_text")),
                    description_text=_text(data.get("description_text")),
                    match_score=round(max(0.0, 1.0 - distance), 4),
                )
            )
        return sorted(results, key=lambda item: (-item.match_score, item.job_key))


def _matches_level(title: str, seniority: str, level: str) -> bool:
    normalized_title = title.casefold()
    if level == "entry":
        return not any(token in normalized_title for token in ("senior", "lead", "manager", "head", "principal"))
    if level == "senior":
        return any(token in normalized_title for token in ("senior", "lead", "principal", "architect")) or seniority in {
            "truong-nhom-giam-sat",
            "quan-ly",
        }
    if level == "manager":
        return any(token in normalized_title for token in ("manager", "head", "director")) or seniority in {
            "quan-ly",
            "giam-doc",
            "pho-giam-doc",
        }
    return True


def _to_date(value: Any) -> datetime.date | None:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _to_datetime(value: Any) -> datetime.datetime | None:
    if isinstance(value, datetime.datetime):
        return value if value.tzinfo else value.replace(tzinfo=datetime.timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=datetime.timezone.utc)
    except ValueError:
        return None


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _string_list(value: Any) -> list[str]:
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return [text for item in values if (text := _text(item))]
