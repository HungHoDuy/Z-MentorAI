from backend.market_scout.pipelines.embed_firestore_jobs_pipeline import EmbedFirestoreJobsPipeline


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
        self.limit_count = None
        self.start_after_id = None

    def order_by(self, field_path: str) -> "FakeCollection":
        ordered = FakeCollection(sorted(self.documents, key=lambda snapshot: snapshot.id))
        ordered.writes = self.writes
        ordered.limit_count = self.limit_count
        ordered.start_after_id = self.start_after_id
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
                        "doc-1",
                        {
                            "company": "ABC",
                            "job_title": "Sales Executive B2B",
                            "min_salary": 12,
                            "max_salary": 17,
                            "min_experience": 2,
                            "Địa điểm làm việc": ["Hồ Chí Minh"],
                        },
                    )
                ]
            ),
            "data_vector_embeddings": FakeCollection(),
        }

    def collection(self, collection_name: str) -> FakeCollection:
        return self.collections[collection_name]

    def batch(self) -> FakeBatch:
        return FakeBatch()


class FakeEmbeddingService:
    model_name = "fake-embedding-model"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


def test_embed_firestore_jobs_pipeline_writes_embedded_documents(monkeypatch) -> None:
    monkeypatch.setattr(EmbedFirestoreJobsPipeline, "_to_firestore_vector", staticmethod(lambda embedding: embedding))
    fake_client = FakeFirestoreClient()
    pipeline = EmbedFirestoreJobsPipeline(
        firestore_client=fake_client,
        embedding_service=FakeEmbeddingService(),
        source_collection="data_for_vectorize",
        vector_collection="data_vector_embeddings",
        batch_size=1,
    )

    result = pipeline.run()

    assert result.scanned_documents == 1
    assert result.embedded_documents == 1
    assert result.written_documents == 1

    written = fake_client.collections["data_vector_embeddings"].writes["doc-1"]
    assert written["source_collection"] == "data_for_vectorize"
    assert written["source_document_id"] == "doc-1"
    assert written["embedding"] == [0.1, 0.2, 0.3]
    assert written["embedding_dimension"] == 3
    assert written["salary_min_vnd"] == 12_000_000
