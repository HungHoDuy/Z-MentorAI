from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from backend.market_scout.repositories.salary_repository import (
    DEFAULT_CLEANED_COLLECTION,
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.services.job_category_taxonomy_service import (
    JobCategoryTaxonomyService,
    normalize_job_category_label,
)


@dataclass(frozen=True)
class ProfileJobCategoryLabelsResult:
    source_collection: str
    taxonomy_version: str
    scanned_documents: int
    documents_with_labels: int
    documents_with_mapped_categories: int
    documents_with_unmatched_labels: int
    documents_with_invalid_labels: int
    distinct_labels: int
    raw_label_occurrences: int
    mapped_label_occurrences: int
    unmatched_label_occurrences: int
    invalid_label_occurrences: int
    mapped_label_coverage: float | None
    top_labels: list[dict[str, Any]]
    top_unmatched_labels: list[dict[str, Any]]
    top_invalid_labels: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_collection": self.source_collection,
            "taxonomy_version": self.taxonomy_version,
            "scanned_documents": self.scanned_documents,
            "documents_with_labels": self.documents_with_labels,
            "documents_with_mapped_categories": self.documents_with_mapped_categories,
            "documents_with_unmatched_labels": self.documents_with_unmatched_labels,
            "documents_with_invalid_labels": self.documents_with_invalid_labels,
            "distinct_labels": self.distinct_labels,
            "raw_label_occurrences": self.raw_label_occurrences,
            "mapped_label_occurrences": self.mapped_label_occurrences,
            "unmatched_label_occurrences": self.unmatched_label_occurrences,
            "invalid_label_occurrences": self.invalid_label_occurrences,
            "mapped_label_coverage": self.mapped_label_coverage,
            "top_labels": list(self.top_labels),
            "top_unmatched_labels": list(self.top_unmatched_labels),
            "top_invalid_labels": list(self.top_invalid_labels),
        }


class ProfileJobCategoryLabelsPipeline:
    """Measure raw-label coverage against the versioned job-category taxonomy."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        taxonomy_service: JobCategoryTaxonomyService | None = None,
        source_collection: str | None = None,
        page_size: int = 500,
        stream_timeout: int = 60,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive.")

        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.taxonomy_service = taxonomy_service or JobCategoryTaxonomyService()
        self.source_collection = source_collection or env_or_default(
            "MARKET_SCOUT_TREND_SOURCE_COLLECTION",
            env_or_default("MARKET_SCOUT_CLEANED_COLLECTION", DEFAULT_CLEANED_COLLECTION),
        )
        self.page_size = page_size
        self.stream_timeout = stream_timeout

    def run(self, *, limit: int | None = None, top_k: int = 100) -> ProfileJobCategoryLabelsResult:
        if top_k <= 0:
            raise ValueError("top_k must be positive.")

        all_counts: Counter[str] = Counter()
        unmatched_counts: Counter[str] = Counter()
        invalid_counts: Counter[str] = Counter()
        display_labels: dict[str, str] = {}
        scanned = 0
        documents_with_labels = 0
        documents_with_mapped = 0
        documents_with_unmatched = 0
        documents_with_invalid = 0

        for snapshot in self._iter_source_snapshots(limit=limit):
            scanned += 1
            labels = self.taxonomy_service.extract_raw_labels(snapshot.to_dict() or {})
            if not labels:
                continue

            documents_with_labels += 1
            match = self.taxonomy_service.classify(labels)
            if match.job_category_ids:
                documents_with_mapped += 1
            if match.unmatched_labels:
                documents_with_unmatched += 1
            if match.invalid_labels:
                documents_with_invalid += 1

            for label in labels:
                key = normalize_job_category_label(label)
                all_counts[key] += 1
                display_labels.setdefault(key, label)
            for label in match.unmatched_labels:
                unmatched_counts[normalize_job_category_label(label)] += 1
            for label in match.invalid_labels:
                invalid_counts[normalize_job_category_label(label)] += 1

        invalid_occurrences = sum(invalid_counts.values())
        unmatched_occurrences = sum(unmatched_counts.values())
        raw_occurrences = sum(all_counts.values())
        mapped_occurrences = raw_occurrences - invalid_occurrences - unmatched_occurrences
        valid_known_or_unknown_occurrences = mapped_occurrences + unmatched_occurrences
        coverage = (
            round(mapped_occurrences / valid_known_or_unknown_occurrences, 4)
            if valid_known_or_unknown_occurrences
            else None
        )

        return ProfileJobCategoryLabelsResult(
            source_collection=self.source_collection,
            taxonomy_version=self.taxonomy_service.taxonomy_version,
            scanned_documents=scanned,
            documents_with_labels=documents_with_labels,
            documents_with_mapped_categories=documents_with_mapped,
            documents_with_unmatched_labels=documents_with_unmatched,
            documents_with_invalid_labels=documents_with_invalid,
            distinct_labels=len(all_counts),
            raw_label_occurrences=raw_occurrences,
            mapped_label_occurrences=mapped_occurrences,
            unmatched_label_occurrences=unmatched_occurrences,
            invalid_label_occurrences=invalid_occurrences,
            mapped_label_coverage=coverage,
            top_labels=self._profile_entries(all_counts, display_labels, top_k),
            top_unmatched_labels=self._profile_entries(unmatched_counts, display_labels, top_k),
            top_invalid_labels=self._profile_entries(invalid_counts, display_labels, top_k),
        )

    def _profile_entries(
        self,
        counts: Counter[str],
        display_labels: dict[str, str],
        top_k: int,
    ) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:top_k]:
            raw_label = display_labels[key]
            definition = self.taxonomy_service.definition_for_label(raw_label)
            entries.append(
                {
                    "raw_label": raw_label,
                    "normalized_label": key,
                    "count": count,
                    "job_category_id": definition.job_category_id if definition else None,
                    "job_family_id": definition.job_family_id if definition else None,
                }
            )
        return entries

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
