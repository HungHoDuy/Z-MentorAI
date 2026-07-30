from __future__ import annotations

from backend.market_scout.pipelines.trend_tracker.embed_job_mapping_pipeline import EmbedJobMappingPipeline
from backend.market_scout.repositories.trend_tracker.trend_job_fact_repository import job_category_trend_fact_from_document
from backend.market_scout.services.trend_tracker.job_mapping_embedding_text_service import (
    JobMappingEmbeddingTextService,
    build_job_mapping_document,
)


class FakeEmbeddingService:
    model_name = "fake-embedding-model"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise AssertionError("dry-run must not call embedding service")

    def embed_query(self, text: str) -> list[float]:
        raise AssertionError("not used")


class FakeSnapshot:
    def __init__(self, document_id: str, data: dict) -> None:
        self.id = document_id
        self._data = data

    def to_dict(self) -> dict:
        return dict(self._data)


class FakeQuery:
    def __init__(self, docs: list[FakeSnapshot]) -> None:
        self.docs = docs
        self.limit_value = len(docs)
        self.after = None
        self.filters: list[tuple[str, str, object]] = []

    def where(self, field_path: str | None = None, op_string: str | None = None, value: object = None, *, filter=None):
        if filter is not None:
            self.filters.append((filter.field_path, filter.op_string, filter.value))
        else:
            self.filters.append((field_path or "", op_string or "", value))
        return self

    def order_by(self, field: str):
        return self

    def limit(self, value: int):
        self.limit_value = value
        return self

    def start_after(self, snapshot: FakeSnapshot):
        self.after = snapshot
        return self

    def stream(self, timeout: int = 60):
        if self.after is not None:
            return []
        docs = self.docs
        for field_path, op_string, value in self.filters:
            if field_path == "source_collection" and op_string == "==":
                docs = [doc for doc in docs if doc.to_dict().get("source_collection") == value]
        return docs[: self.limit_value]


class FakeFirestoreClient:
    def __init__(self, docs: list[FakeSnapshot]) -> None:
        self.docs = docs
        self.last_query: FakeQuery | None = None

    def collection(self, name: str):
        self.last_query = FakeQuery(self.docs)
        return self.last_query


def test_job_mapping_embedding_text_uses_stable_relevant_fields() -> None:
    service = JobMappingEmbeddingTextService(requirements_max_chars=80, description_max_chars=80)

    text = service.build_text("job-1", _fact_data())

    assert "Job title: Backend Developer" in text
    assert "Job categories: software_it" in text
    assert "Job families: digital_telecom" in text
    assert "Raw category labels: CNTT - Phần mềm" in text
    assert "Requirements: Python backend API cloud" in text
    assert "min_salary" not in text
    assert "company" not in text.casefold()


def test_embed_job_mapping_pipeline_dry_run_counts_valid_facts() -> None:
    docs = [
        FakeSnapshot("job-1", _fact_data()),
        FakeSnapshot("job-2", {"job_title": "Missing taxonomy"}),
    ]
    pipeline = EmbedJobMappingPipeline(
        firestore_client=FakeFirestoreClient(docs),
        embedding_service=FakeEmbeddingService(),
        source_collection="trend_job_facts_v2",
        embedding_collection="job_mapping_embedding",
        batch_size=2,
        page_size=10,
    )

    result = pipeline.run(dry_run=True)

    assert result.scanned_documents == 2
    assert result.embedded_documents == 1
    assert result.written_documents == 0
    assert result.skipped_documents == 1
    assert result.embedding_collection == "job_mapping_embedding"
    assert result.embedding_model == "fake-embedding-model"


def test_embed_job_mapping_pipeline_filters_by_source_collection() -> None:
    docs = [
        FakeSnapshot("job-weekly", {**_fact_data(), "source_collection": "data_for_vectorize_2026W31"}),
        FakeSnapshot("job-old", {**_fact_data(), "source_collection": "data_for_vectorize"}),
    ]
    firestore_client = FakeFirestoreClient(docs)
    pipeline = EmbedJobMappingPipeline(
        firestore_client=firestore_client,
        embedding_service=FakeEmbeddingService(),
        source_collection="trend_job_facts_v2",
        embedding_collection="job_mapping_embedding",
        source_collection_filter="data_for_vectorize_2026W31",
        batch_size=2,
        page_size=10,
    )

    result = pipeline.run(dry_run=True)

    assert result.scanned_documents == 1
    assert result.embedded_documents == 1
    assert firestore_client.last_query is not None
    assert ("source_collection", "==", "data_for_vectorize_2026W31") in firestore_client.last_query.filters


def _fact_data() -> dict:
    return {
        "job_key": "job-1",
        "source": "careerviet",
        "job_title": "Backend Developer",
        "location_ids": ["ha-noi"],
        "seniority": "Nhân viên",
        "employment_type": "Nhân viên chính thức",
        "is_active": True,
        "requirements_text": "Python backend API cloud",
        "description_text": "Build backend services and integrate databases",
        "raw_job_category_labels": ["CNTT - Phần mềm"],
        "job_category_ids": ["software_it"],
        "job_family_ids": ["digital_telecom"],
        "taxonomy_version": "job-category-taxonomy-v1",
        "company": "Example Co",
        "min_salary": 10,
    }


def test_job_mapping_document_keeps_only_runtime_mapping_fields() -> None:
    fact = job_category_trend_fact_from_document("job-1", _fact_data())
    assert fact is not None

    document = build_job_mapping_document(
        document_id="job-1",
        source_collection="trend_job_facts_v2",
        fact=fact,
        embedding_text="Job title: Backend Developer",
        embedding_model="fake-embedding-model",
        embedding_updated_at="2026-06-30T00:00:00+00:00",
    )

    assert set(document) == {
        "job_key",
        "source_document_id",
        "job_url",
        "job_title",
        "company",
        "location_ids",
        "source_expires_at",
        "raw_job_category_labels",
        "job_category_ids",
        "job_family_ids",
        "embedding_text",
        "embedding_model",
        "embedding_updated_at",
    }
    assert "source_collection" not in document
    assert "source" not in document
    assert "source_job_id" not in document
    assert "company_key" not in document
    assert "seniority" not in document
    assert "is_active" not in document
    assert "taxonomy_version" not in document
    assert "embedding_use_cases" not in document