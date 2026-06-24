from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.market_scout.repositories.salary_benchmark.salary_repository import (
    DEFAULT_CLEANED_COLLECTION,
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.schemas.salary_benchmark.salary import SalaryJobRecord
from backend.market_scout.services.salary_benchmark.job_embedding_text_service import JobEmbeddingTextService
from backend.market_scout.services.salary_benchmark.vertex_embedding_service import EmbeddingService, VertexTextEmbeddingService


DEFAULT_VECTOR_COLLECTION = "data_vector_embeddings"
DEFAULT_EMBEDDING_FIELD = "embedding"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmbedFirestoreJobsResult:
    status: str
    source_collection: str
    vector_collection: str
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
            "vector_collection": self.vector_collection,
            "scanned_documents": self.scanned_documents,
            "embedded_documents": self.embedded_documents,
            "written_documents": self.written_documents,
            "skipped_documents": self.skipped_documents,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "dry_run": self.dry_run,
        }


class EmbedFirestoreJobsPipeline:
    """Embed jobs from one Firestore collection and save vector-search documents to another collection."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        embedding_service: EmbeddingService | None = None,
        text_service: JobEmbeddingTextService | None = None,
        source_collection: str | None = None,
        vector_collection: str | None = None,
        embedding_field: str | None = None,
        batch_size: int = 10,
        page_size: int = 100,
        stream_timeout: int = 60,
        logger: logging.Logger | None = None,
    ) -> None:
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.embedding_service = embedding_service or VertexTextEmbeddingService()
        self.text_service = text_service or JobEmbeddingTextService()
        self.source_collection = source_collection or env_or_default(
            "MARKET_SCOUT_VECTOR_SOURCE_COLLECTION",
            env_or_default("MARKET_SCOUT_CLEANED_COLLECTION", DEFAULT_CLEANED_COLLECTION),
        )
        self.vector_collection = vector_collection or env_or_default(
            "MARKET_SCOUT_VECTOR_COLLECTION",
            DEFAULT_VECTOR_COLLECTION,
        )
        self.embedding_field = embedding_field or env_or_default(
            "MARKET_SCOUT_VECTOR_FIELD",
            DEFAULT_EMBEDDING_FIELD,
        )
        self.batch_size = batch_size
        self.page_size = page_size
        self.stream_timeout = stream_timeout
        self.logger = logger or LOGGER

    def run(
        self,
        *,
        limit: int | None = None,
        dry_run: bool = False,
        require_salary: bool = True,
    ) -> EmbedFirestoreJobsResult:
        self.logger.info(
            "Starting embedding pipeline: source=%s vector=%s batch_size=%s page_size=%s dry_run=%s",
            self.source_collection,
            self.vector_collection,
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
            if scanned == 1 or scanned % 100 == 0:
                self.logger.info(
                    "Progress: scanned=%s embedded=%s written=%s skipped=%s current_doc=%s",
                    scanned,
                    embedded,
                    written,
                    skipped,
                    snapshot.id,
                )
            data = snapshot.to_dict() or {}
            record = SalaryJobRecord.from_firestore(snapshot.id, data)
            if record is None or (require_salary and not record.has_salary):
                skipped += 1
                continue

            embedding_text = self.text_service.build_text(snapshot.id, data)
            if not embedding_text:
                skipped += 1
                continue

            target_data = self._build_target_document(snapshot.id, data, record, embedding_text)
            pending.append((snapshot.id, target_data, embedding_text))

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
            "Finished embedding pipeline: scanned=%s embedded=%s written=%s skipped=%s",
            scanned,
            embedded,
            written,
            skipped,
        )

        return EmbedFirestoreJobsResult(
            status="success",
            source_collection=self.source_collection,
            vector_collection=self.vector_collection,
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
        page_number = 0

        while True:
            current_page_size = self.page_size
            if limit is not None:
                remaining = limit - yielded
                if remaining <= 0:
                    break
                current_page_size = min(current_page_size, remaining)

            query = collection_ref.order_by("__name__").limit(current_page_size)
            if last_snapshot is not None:
                query = query.start_after(last_snapshot)

            self.logger.info(
                "Reading Firestore page %s: requested_page_size=%s start_after=%s",
                page_number + 1,
                current_page_size,
                last_snapshot.id if last_snapshot is not None else None,
            )
            page = list(query.stream(timeout=self.stream_timeout))
            if not page:
                self.logger.info("No more Firestore documents after %s pages.", page_number)
                break

            page_number += 1
            self.logger.info(
                "Read Firestore page %s: count=%s first_doc=%s last_doc=%s total_yielded_before_page=%s",
                page_number,
                len(page),
                page[0].id,
                page[-1].id,
                yielded,
            )

            for snapshot in page:
                yield snapshot
                yielded += 1

            last_snapshot = page[-1]

    def _flush(self, pending: list[tuple[str, dict[str, Any], str]], *, dry_run: bool) -> dict[str, int | None]:
        self.logger.info(
            "Flushing batch: size=%s first_doc=%s last_doc=%s dry_run=%s",
            len(pending),
            pending[0][0] if pending else None,
            pending[-1][0] if pending else None,
            dry_run,
        )
        if dry_run:
            return {
                "embedded": len(pending),
                "written": 0,
                "embedding_dimension": None,
            }

        texts = [item[2] for item in pending]
        self.logger.info("Requesting embeddings: count=%s model=%s", len(texts), self.embedding_service.model_name)
        embeddings = self.embedding_service.embed_documents(texts)
        if len(embeddings) != len(pending):
            raise RuntimeError("Embedding service returned a different number of embeddings than requested.")
        self.logger.info(
            "Received embeddings: count=%s dimension=%s",
            len(embeddings),
            len(embeddings[0]) if embeddings else None,
        )

        vector_collection_ref = self.firestore_client.collection(self.vector_collection)
        batch = self.firestore_client.batch()

        for (document_id, target_data, _), embedding in zip(pending, embeddings, strict=True):
            target_data[self.embedding_field] = self._to_firestore_vector(embedding)
            target_data["embedding_dimension"] = len(embedding)
            batch.set(vector_collection_ref.document(document_id), target_data, merge=True)

        self.logger.info("Committing Firestore batch: count=%s collection=%s", len(pending), self.vector_collection)
        batch.commit()
        self.logger.info("Committed Firestore batch: count=%s", len(pending))
        return {
            "embedded": len(pending),
            "written": len(pending),
            "embedding_dimension": len(embeddings[0]) if embeddings else None,
        }

    def _build_target_document(
        self,
        document_id: str,
        source_data: dict[str, Any],
        record: SalaryJobRecord,
        embedding_text: str,
    ) -> dict[str, Any]:
        document = record.to_dict()
        document.update(
            {
                "source_collection": self.source_collection,
                "source_document_id": document_id,
                "embedding_text": embedding_text,
                "embedding_model": self.embedding_service.model_name,
                "embedding_updated_at": datetime.now(timezone.utc).isoformat(),
                "has_salary": record.has_salary,
                "raw_min_salary": source_data.get("min_salary"),
                "raw_max_salary": source_data.get("max_salary"),
            }
        )
        return document

    @staticmethod
    def _to_firestore_vector(embedding: list[float]):
        try:
            from google.cloud.firestore_v1.vector import Vector
        except ImportError as exc:
            raise RuntimeError(
                "Missing google-cloud-firestore vector support. Upgrade google-cloud-firestore in requirements.txt."
            ) from exc

        return Vector(embedding)
