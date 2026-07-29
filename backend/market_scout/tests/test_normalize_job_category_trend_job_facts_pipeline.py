from datetime import date

from backend.market_scout.pipelines.trend_tracker.normalize_job_category_trend_job_facts_pipeline import (
    NormalizeJobCategoryTrendJobFactsPipeline,
)


class FakeSnapshot:
    def __init__(self, document_id: str, data: dict) -> None:
        self.id = document_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class FakeDocumentRef:
    def __init__(self, collection: "FakeCollection", document_id: str) -> None:
        self.collection = collection
        self.document_id = document_id


class FakeCollection:
    def __init__(self, documents: list[FakeSnapshot] | None = None) -> None:
        self.documents = documents or []
        self.writes: dict[str, dict] = {}
        self.limit_count: int | None = None
        self.start_after_id: str | None = None

    def order_by(self, field_path: str) -> "FakeCollection":
        ordered = FakeCollection(sorted(self.documents, key=lambda snapshot: snapshot.id))
        ordered.writes = self.writes
        return ordered

    def limit(self, limit_count: int) -> "FakeCollection":
        limited = FakeCollection(self.documents)
        limited.writes = self.writes
        limited.limit_count = limit_count
        limited.start_after_id = self.start_after_id
        return limited

    def start_after(self, snapshot: FakeSnapshot) -> "FakeCollection":
        started = FakeCollection(self.documents)
        started.writes = self.writes
        started.limit_count = self.limit_count
        started.start_after_id = snapshot.id
        return started

    def stream(self, timeout: int | None = None):
        documents = self.documents
        if self.start_after_id is not None:
            documents = [document for document in documents if document.id > self.start_after_id]
        if self.limit_count is not None:
            documents = documents[: self.limit_count]
        return iter(documents)

    def document(self, document_id: str) -> FakeDocumentRef:
        return FakeDocumentRef(self, document_id)


class FakeBatch:
    def __init__(self) -> None:
        self.operations: list[tuple[FakeDocumentRef, dict]] = []

    def set(self, document_ref: FakeDocumentRef, data: dict, merge: bool = True) -> None:
        self.operations.append((document_ref, data))

    def commit(self) -> None:
        for document_ref, data in self.operations:
            document_ref.collection.writes[document_ref.document_id] = data


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.collections = {
            "data_for_vectorize": FakeCollection(
                [
                    FakeSnapshot(
                        "raw-1",
                        {
                            "job_id": "35C19E7E",
                            "job_title": "QA Staff",
                            "company": "Example Foods",
                            "location": ["HCM"],
                            "Ngành nghề": "Quản lý chất lượng (QA/QC), Thực phẩm & Đồ uống",
                            "updated_at": "2026-06-17",
                            "expires_at": "2026-06-30",
                        },
                    ),
                    FakeSnapshot("raw-2", {"job_id": "2", "job_title": "No category"}),
                    FakeSnapshot("invalid", {"company": "Missing title"}),
                ]
            ),
            "trend_job_facts_v2": FakeCollection(),
        }

    def collection(self, collection_name: str) -> FakeCollection:
        return self.collections[collection_name]

    def batch(self) -> FakeBatch:
        return FakeBatch()


def test_normalization_pipeline_writes_job_category_facts_and_reports_missing_categories() -> None:
    fake_client = FakeFirestoreClient()
    result = NormalizeJobCategoryTrendJobFactsPipeline(
        firestore_client=fake_client,
        source_collection="data_for_vectorize",
        fact_collection="trend_job_facts_v2",
        page_size=1,
        batch_size=1,
    ).run(observed_at=date(2026, 6, 20))

    assert result.scanned_documents == 3
    assert result.normalized_documents == 2
    assert result.documents_without_job_categories == 1
    assert result.documents_with_unmatched_job_categories == 0
    assert result.documents_with_invalid_job_categories == 0
    assert result.written_documents == 2
    assert result.skipped_documents == 1

    written = fake_client.collections["trend_job_facts_v2"].writes["careerviet:35C19E7E"]
    assert written["job_category_ids"] == ["quality_assurance", "food_beverage"]
    assert written["job_family_ids"] == ["operations", "people_services"]
    assert written["taxonomy_version"] == "job-category-taxonomy-v1"
    assert written["normalizer_version"] == "job-category-trend-job-fact-v2"
