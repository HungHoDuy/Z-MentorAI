from backend.market_scout.pipelines.profile_job_category_labels_pipeline import (
    ProfileJobCategoryLabelsPipeline,
)


class FakeSnapshot:
    def __init__(self, document_id: str, data: dict) -> None:
        self.id = document_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class FakeCollection:
    def __init__(self, documents: list[FakeSnapshot]) -> None:
        self.documents = documents
        self.limit_count: int | None = None
        self.start_after_id: str | None = None

    def order_by(self, field_path: str) -> "FakeCollection":
        return FakeCollection(sorted(self.documents, key=lambda snapshot: snapshot.id))

    def limit(self, limit_count: int) -> "FakeCollection":
        limited = FakeCollection(self.documents)
        limited.limit_count = limit_count
        limited.start_after_id = self.start_after_id
        return limited

    def start_after(self, snapshot: FakeSnapshot) -> "FakeCollection":
        started = FakeCollection(self.documents)
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


class FakeFirestoreClient:
    def __init__(self) -> None:
        self.collection_ref = FakeCollection(
            [
                FakeSnapshot("raw-1", {"Ngành nghề": "Kế toán / Kiểm toán, Tỉnh"}),
                FakeSnapshot("raw-2", {"Ngành nghề": "CNTT - Phần mềm, Nhãn lạ"}),
                FakeSnapshot("raw-3", {"job_title": "Missing category"}),
            ]
        )

    def collection(self, collection_name: str) -> FakeCollection:
        assert collection_name == "data_for_vectorize"
        return self.collection_ref


def test_profile_reports_mapping_coverage_unmatched_and_invalid_labels() -> None:
    result = ProfileJobCategoryLabelsPipeline(
        firestore_client=FakeFirestoreClient(),
        source_collection="data_for_vectorize",
        page_size=1,
    ).run(top_k=10)

    assert result.scanned_documents == 3
    assert result.documents_with_labels == 2
    assert result.documents_with_mapped_categories == 2
    assert result.documents_with_unmatched_labels == 1
    assert result.documents_with_invalid_labels == 1
    assert result.distinct_labels == 4
    assert result.raw_label_occurrences == 4
    assert result.mapped_label_occurrences == 2
    assert result.unmatched_label_occurrences == 1
    assert result.invalid_label_occurrences == 1
    assert result.mapped_label_coverage == 0.6667
    assert result.top_unmatched_labels == [
        {
            "raw_label": "Nhãn lạ",
            "normalized_label": "nhan la",
            "count": 1,
            "job_category_id": None,
            "job_family_id": None,
        }
    ]
