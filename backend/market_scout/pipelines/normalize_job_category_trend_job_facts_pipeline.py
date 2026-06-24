from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from backend.market_scout.repositories.salary_repository import (
    DEFAULT_CLEANED_COLLECTION,
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.services.job_category_trend_job_fact_normalizer import (
    JobCategoryTrendJobFactNormalizer,
)


DEFAULT_JOB_CATEGORY_TREND_FACT_COLLECTION = "trend_job_facts_v2"
DEFAULT_PAGE_SIZE = 500
DEFAULT_BATCH_SIZE = 400
NORMALIZER_VERSION = "job-category-trend-job-fact-v2"
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class NormalizeJobCategoryTrendJobFactsResult:
    status: str
    source_collection: str
    fact_collection: str
    scanned_documents: int
    normalized_documents: int
    documents_without_job_categories: int
    documents_with_unmatched_job_categories: int
    documents_with_invalid_job_categories: int
    written_documents: int
    skipped_documents: int
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "source_collection": self.source_collection,
            "fact_collection": self.fact_collection,
            "scanned_documents": self.scanned_documents,
            "normalized_documents": self.normalized_documents,
            "documents_without_job_categories": self.documents_without_job_categories,
            "documents_with_unmatched_job_categories": self.documents_with_unmatched_job_categories,
            "documents_with_invalid_job_categories": self.documents_with_invalid_job_categories,
            "written_documents": self.written_documents,
            "skipped_documents": self.skipped_documents,
            "dry_run": self.dry_run,
        }


class NormalizeJobCategoryTrendJobFactsPipeline:
    """Materialize raw jobs as taxonomy-backed facts for the v2 trend pipeline."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        normalizer: JobCategoryTrendJobFactNormalizer | None = None,
        source_collection: str | None = None,
        fact_collection: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        stream_timeout: int = 60,
        logger: logging.Logger | None = None,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive.")
        if batch_size <= 0 or batch_size > 500:
            raise ValueError("batch_size must be between 1 and 500.")

        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.normalizer = normalizer or JobCategoryTrendJobFactNormalizer()
        self.source_collection = source_collection or env_or_default(
            "MARKET_SCOUT_TREND_SOURCE_COLLECTION",
            env_or_default("MARKET_SCOUT_CLEANED_COLLECTION", DEFAULT_CLEANED_COLLECTION),
        )
        self.fact_collection = fact_collection or env_or_default(
            "MARKET_SCOUT_JOB_CATEGORY_TREND_FACT_COLLECTION",
            DEFAULT_JOB_CATEGORY_TREND_FACT_COLLECTION,
        )
        self.page_size = page_size
        self.batch_size = batch_size
        self.stream_timeout = stream_timeout
        self.logger = logger or LOGGER

    def run(
        self,
        *,
        limit: int | None = None,
        observed_at: date | None = None,
        dry_run: bool = False,
    ) -> NormalizeJobCategoryTrendJobFactsResult:
        self.logger.info(
            "Starting job-category trend normalization: source=%s facts=%s dry_run=%s",
            self.source_collection,
            self.fact_collection,
            dry_run,
        )

        scanned = 0
        normalized = 0
        without_categories = 0
        with_unmatched = 0
        with_invalid = 0
        skipped = 0
        written = 0
        pending: list[tuple[str, dict[str, Any]]] = []

        for snapshot in self._iter_source_snapshots(limit=limit):
            scanned += 1
            fact = self.normalizer.normalize(
                snapshot.id,
                snapshot.to_dict() or {},
                observed_at=observed_at,
            )
            if fact is None:
                skipped += 1
                continue

            normalized += 1
            if not fact.job_category_ids:
                without_categories += 1
            if fact.unmatched_job_category_labels:
                with_unmatched += 1
            if fact.invalid_job_category_labels:
                with_invalid += 1
            pending.append(
                (
                    job_category_trend_fact_document_id(fact.job_key),
                    self._build_fact_document(snapshot.id, fact),
                )
            )
            if len(pending) >= self.batch_size:
                written += self._flush(pending, dry_run=dry_run)
                pending = []

        if pending:
            written += self._flush(pending, dry_run=dry_run)

        self.logger.info(
            "Finished job-category trend normalization: scanned=%s normalized=%s without_categories=%s unmatched=%s invalid=%s skipped=%s written=%s",
            scanned,
            normalized,
            without_categories,
            with_unmatched,
            with_invalid,
            skipped,
            written,
        )
        return NormalizeJobCategoryTrendJobFactsResult(
            status="success",
            source_collection=self.source_collection,
            fact_collection=self.fact_collection,
            scanned_documents=scanned,
            normalized_documents=normalized,
            documents_without_job_categories=without_categories,
            documents_with_unmatched_job_categories=with_unmatched,
            documents_with_invalid_job_categories=with_invalid,
            written_documents=written,
            skipped_documents=skipped,
            dry_run=dry_run,
        )

    def _iter_source_snapshots(self, *, limit: int | None = None):
        collection_ref = self.firestore_client.collection(self.source_collection)
        last_snapshot = None
        yielded = 0

        while True:
            page_size = self.page_size
            if limit is not None:
                remaining = limit - yielded
                if remaining <= 0:
                    return
                page_size = min(page_size, remaining)

            query = collection_ref.order_by("__name__").limit(page_size)
            if last_snapshot is not None:
                query = query.start_after(last_snapshot)
            page = list(query.stream(timeout=self.stream_timeout))
            if not page:
                return

            for snapshot in page:
                yield snapshot
                yielded += 1
            last_snapshot = page[-1]

    def _flush(self, pending: list[tuple[str, dict[str, Any]]], *, dry_run: bool) -> int:
        if dry_run:
            return 0

        collection_ref = self.firestore_client.collection(self.fact_collection)
        batch = self.firestore_client.batch()
        for document_id, document in pending:
            batch.set(collection_ref.document(document_id), document, merge=True)
        batch.commit()
        return len(pending)

    def _build_fact_document(self, source_document_id: str, fact: Any) -> dict[str, Any]:
        document = fact.to_dict()
        document.update(
            {
                "source_collection": self.source_collection,
                "source_document_id": source_document_id,
                "normalizer_version": NORMALIZER_VERSION,
            }
        )
        return document


def job_category_trend_fact_document_id(job_key: str) -> str:
    return job_key.replace("/", "-").strip() or "unknown-job"
