from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.market_scout.repositories.salary_benchmark.salary_repository import (
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.repositories.trend_tracker.trend_job_fact_repository import (
    DEFAULT_TREND_FACT_COLLECTION,
    job_category_trend_fact_from_document,
)
from backend.market_scout.services.salary_benchmark.vertex_embedding_service import EmbeddingService, VertexTextEmbeddingService
from backend.market_scout.services.trend_tracker.job_mapping_embedding_text_service import (
    JobMappingEmbeddingTextService,
    build_job_mapping_document,
)


DEFAULT_JOB_MAPPING_EMBEDDING_COLLECTION = "job_mapping_embedding"
DEFAULT_EMBEDDING_FIELD = "embedding"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbedJobMappingResult:
    status: str
    source_collection: str
    embedding_collection: str
    scanned_documents: int
    embedded_documents: int
    written_documents: int
    skipped_documents: int
    embedding_model: str
    embedding_dimension: int | None
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_collection": self.source_collection,
            "embedding_collection": self.embedding_collection,
            "scanned_documents": self.scanned_documents,
            "embedded_documents": self.embedded_documents,
            "written_documents": self.written_documents,
            "skipped_documents": self.skipped_documents,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "dry_run": self.dry_run,
        }


class EmbedJobMappingPipeline:
    """Embed trend job facts into a reusable job-mapping vector collection."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        embedding_service: EmbeddingService | None = None,
        text_service: JobMappingEmbeddingTextService | None = None,
        source_collection: str | None = None,
        embedding_collection: str | None = None,
        embedding_field: str | None = None,
        source_collection_filter: str | None = None,
        batch_size: int = 10,
        page_size: int = 100,
        stream_timeout: int = 60,
        logger: logging.Logger | None = None,
    ) -> None:
        if batch_size <= 0 or page_size <= 0:
            raise ValueError("batch_size and page_size must be positive.")
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.embedding_service = embedding_service or VertexTextEmbeddingService()
        self.text_service = text_service or JobMappingEmbeddingTextService()
        self.source_collection = source_collection or env_or_default(
            "MARKET_SCOUT_JOB_MAPPING_SOURCE_COLLECTION",
            DEFAULT_TREND_FACT_COLLECTION,
        )
        self.embedding_collection = embedding_collection or env_or_default(
            "MARKET_SCOUT_JOB_MAPPING_EMBEDDING_COLLECTION",
            DEFAULT_JOB_MAPPING_EMBEDDING_COLLECTION,
        )
        self.embedding_field = embedding_field or env_or_default(
            "MARKET_SCOUT_JOB_MAPPING_EMBEDDING_FIELD",
            DEFAULT_EMBEDDING_FIELD,
        )
        self.source_collection_filter = source_collection_filter
        self.batch_size = batch_size
        self.page_size = page_size
        self.stream_timeout = stream_timeout
        self.logger = logger or LOGGER

    def run(self, *, limit: int | None = None, dry_run: bool = False) -> EmbedJobMappingResult:
        self.logger.info(
            "Starting job mapping embedding pipeline: source=%s target=%s source_collection_filter=%s batch_size=%s page_size=%s dry_run=%s",
            self.source_collection,
            self.embedding_collection,
            self.source_collection_filter,
            self.batch_size,
            self.page_size,
            dry_run,
        )

        scanned = 0
        embedded = 0
        written = 0
        skipped = 0
        embedding_dimension: int | None = None
        pending: list[tuple[str, dict[str, Any], str]] = []

        for snapshot in self._iter_source_snapshots(limit=limit):
            scanned += 1
            data = snapshot.to_dict() or {}
            fact = job_category_trend_fact_from_document(snapshot.id, data)
            if fact is None or not fact.job_category_ids or not fact.job_family_ids:
                skipped += 1
                continue

            embedding_text = self.text_service.build_text_from_fact(fact)
            if not embedding_text:
                skipped += 1
                continue

            target_document = build_job_mapping_document(
                document_id=snapshot.id,
                source_collection=self.source_collection,
                fact=fact,
                embedding_text=embedding_text,
                embedding_model=self.embedding_service.model_name,
                embedding_updated_at=datetime.now(timezone.utc).isoformat(),
            )
            pending.append((fact.job_key, target_document, embedding_text))

            if len(pending) >= self.batch_size:
                batch_result = self._flush(pending, dry_run=dry_run)
                embedded += batch_result["embedded"]
                written += batch_result["written"]
                embedding_dimension = embedding_dimension or batch_result["embedding_dimension"]
                pending = []

        if pending:
            batch_result = self._flush(pending, dry_run=dry_run)
            embedded += batch_result["embedded"]
            written += batch_result["written"]
            embedding_dimension = embedding_dimension or batch_result["embedding_dimension"]

        self.logger.info(
            "Finished job mapping embedding pipeline: scanned=%s embedded=%s written=%s skipped=%s",
            scanned,
            embedded,
            written,
            skipped,
        )
        return EmbedJobMappingResult(
            status="success",
            source_collection=self.source_collection,
            embedding_collection=self.embedding_collection,
            scanned_documents=scanned,
            embedded_documents=embedded,
            written_documents=written,
            skipped_documents=skipped,
            embedding_model=self.embedding_service.model_name,
            embedding_dimension=embedding_dimension,
            dry_run=dry_run,
        )

    def _iter_source_snapshots(self, *, limit: int | None = None):
        collection_ref = self.firestore_client.collection(self.source_collection)
        last_snapshot = None
        yielded = 0

        while True:
            current_page_size = self.page_size
            if limit is not None:
                remaining = limit - yielded
                if remaining <= 0:
                    break
                current_page_size = min(current_page_size, remaining)

            query = collection_ref
            if self.source_collection_filter:
                query = _apply_where(query, "source_collection", "==", self.source_collection_filter)
            query = query.order_by("__name__").limit(current_page_size)
            if last_snapshot is not None:
                query = query.start_after(last_snapshot)

            page = list(query.stream(timeout=self.stream_timeout))
            if not page:
                break

            for snapshot in page:
                yield snapshot
                yielded += 1

            last_snapshot = page[-1]

    def _flush(self, pending: list[tuple[str, dict[str, Any], str]], *, dry_run: bool) -> dict[str, int | None]:
        if dry_run:
            return {"embedded": len(pending), "written": 0, "embedding_dimension": None}

        texts = [item[2] for item in pending]
        embeddings = self.embedding_service.embed_documents(texts)
        if len(embeddings) != len(pending):
            raise RuntimeError("Embedding service returned a different number of embeddings than requested.")

        collection_ref = self.firestore_client.collection(self.embedding_collection)
        batch = self.firestore_client.batch()
        for (document_id, target_data, _), embedding in zip(pending, embeddings, strict=True):
            target_data[self.embedding_field] = self._to_firestore_vector(embedding)
            target_data["embedding_dimension"] = len(embedding)
            batch.set(collection_ref.document(document_id), target_data, merge=True)
        batch.commit()
        return {
            "embedded": len(pending),
            "written": len(pending),
            "embedding_dimension": len(embeddings[0]) if embeddings else None,
        }

    @staticmethod
    def _to_firestore_vector(embedding: list[float]):
        try:
            from google.cloud.firestore_v1.vector import Vector
        except ImportError as exc:
            raise RuntimeError(
                "Missing google-cloud-firestore vector support. Upgrade google-cloud-firestore in requirements.txt."
            ) from exc
        return Vector(embedding)

def _apply_where(query: Any, field_path: str, operator: str, value: Any) -> Any:
    try:
        from google.cloud.firestore_v1.base_query import FieldFilter

        return query.where(filter=FieldFilter(field_path, operator, value))
    except (ImportError, TypeError):
        return query.where(field_path, operator, value)