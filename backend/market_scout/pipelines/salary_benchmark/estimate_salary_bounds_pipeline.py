from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.market_scout.pipelines.salary_benchmark.embed_firestore_jobs_pipeline import DEFAULT_VECTOR_COLLECTION
from backend.market_scout.repositories.salary_benchmark.salary_repository import build_firestore_client, env_or_default, load_env_file
from backend.market_scout.services.salary_benchmark.salary_bound_estimation_service import SalaryBoundEstimationService


@dataclass(frozen=True)
class EstimateSalaryBoundsResult:
    status: str
    collection: str
    scanned_documents: int
    updated_documents: int
    skipped_documents: int
    salary_factor: float
    max_salary_sentinel: float | None
    dry_run: bool
    source_collection_filter: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "collection": self.collection,
            "scanned_documents": self.scanned_documents,
            "updated_documents": self.updated_documents,
            "skipped_documents": self.skipped_documents,
            "salary_factor": self.salary_factor,
            "max_salary_sentinel": self.max_salary_sentinel,
            "dry_run": self.dry_run,
            "source_collection_filter": self.source_collection_filter,
        }


class EstimateSalaryBoundsPipeline:
    """Update open-ended salary ranges in an existing Firestore collection."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        collection_name: str | None = None,
        service: SalaryBoundEstimationService | None = None,
        page_size: int = 500,
        stream_timeout: int = 60,
        batch_size: int = 400,
        source_collection_filter: str | None = None,
    ) -> None:
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.collection_name = collection_name or env_or_default(
            "MARKET_SCOUT_VECTOR_COLLECTION",
            DEFAULT_VECTOR_COLLECTION,
        )
        self.service = service or SalaryBoundEstimationService()
        self.page_size = page_size
        self.stream_timeout = stream_timeout
        self.batch_size = batch_size
        self.source_collection_filter = source_collection_filter

    def run(self, *, limit: int | None = None, dry_run: bool = False) -> EstimateSalaryBoundsResult:
        documents = list(self._iter_documents(limit=limit))
        max_salary_sentinel_vnd = self.service.detect_max_salary_sentinel(documents)
        salary_factor = self.service.calculate_factor(
            documents,
            max_salary_sentinel_vnd=max_salary_sentinel_vnd,
        )

        collection_ref = self.firestore_client.collection(self.collection_name)
        batch = self.firestore_client.batch()
        pending = 0
        updated = 0
        skipped = 0

        for document_id, data in documents:
            estimate = self.service.estimate(
                document_id,
                data,
                salary_factor,
                max_salary_sentinel_vnd=max_salary_sentinel_vnd,
            )
            if estimate is None:
                skipped += 1
                continue

            updated += 1
            if dry_run:
                continue

            batch.set(
                collection_ref.document(document_id),
                {
                    "min_salary": estimate.min_salary,
                    "max_salary": estimate.max_salary,
                    "salary_factor": estimate.salary_factor,
                },
                merge=True,
            )
            pending += 1

            if pending >= self.batch_size:
                batch.commit()
                batch = self.firestore_client.batch()
                pending = 0

        if pending:
            batch.commit()

        return EstimateSalaryBoundsResult(
            status="success",
            collection=self.collection_name,
            scanned_documents=len(documents),
            updated_documents=updated,
            skipped_documents=skipped,
            salary_factor=salary_factor,
            max_salary_sentinel=(
                round(max_salary_sentinel_vnd / 1_000_000, 2)
                if max_salary_sentinel_vnd is not None
                else None
            ),
            dry_run=dry_run,
            source_collection_filter=self.source_collection_filter,
        )

    def _iter_documents(self, *, limit: int | None = None):
        collection_ref = self.firestore_client.collection(self.collection_name)
        base_query = collection_ref
        if self.source_collection_filter:
            base_query = base_query.where("source_collection", "==", self.source_collection_filter)

        last_snapshot = None
        yielded = 0

        while True:
            current_page_size = self.page_size
            if limit is not None:
                remaining = limit - yielded
                if remaining <= 0:
                    break
                current_page_size = min(current_page_size, remaining)

            query = base_query.order_by("__name__").limit(current_page_size)
            if last_snapshot is not None:
                query = query.start_after(last_snapshot)

            page = list(query.stream(timeout=self.stream_timeout))
            if not page:
                break

            for snapshot in page:
                yield snapshot.id, snapshot.to_dict() or {}
                yielded += 1

            last_snapshot = page[-1]
