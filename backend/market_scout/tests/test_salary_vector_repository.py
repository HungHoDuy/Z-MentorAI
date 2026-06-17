from backend.market_scout.repositories.salary_vector_repository import SalaryVectorRepository


class FakeSnapshot:
    def __init__(self, document_id: str, data: dict) -> None:
        self.id = document_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class FakeVectorQuery:
    def __init__(self, snapshots: list[FakeSnapshot]) -> None:
        self.snapshots = snapshots
        self.stream_timeout = None

    def stream(self, timeout: int | None = None):
        self.stream_timeout = timeout
        return iter(self.snapshots)


class FakeCollection:
    def __init__(self, snapshots: list[FakeSnapshot]) -> None:
        self.snapshots = snapshots
        self.find_nearest_args = None
        self.last_vector_query = None

    def find_nearest(self, **kwargs) -> FakeVectorQuery:
        self.find_nearest_args = kwargs
        self.last_vector_query = FakeVectorQuery(self.snapshots)
        return self.last_vector_query


class FakeFirestoreClient:
    def __init__(self, snapshots: list[FakeSnapshot]) -> None:
        self.collection_name = None
        self.collection_ref = FakeCollection(snapshots)

    def collection(self, collection_name: str) -> FakeCollection:
        self.collection_name = collection_name
        return self.collection_ref


class FakeEmbeddingService:
    model_name = "fake-query-embedding"

    def __init__(self) -> None:
        self.last_query_text = None

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        self.last_query_text = text
        return [0.1, 0.2, 0.3]


def test_salary_vector_repository_searches_firestore_vectors_and_returns_filtered_records() -> None:
    snapshots = [
        FakeSnapshot(
            "match",
            {
                "job_title": "Sales Executive B2B",
                "company": "ABC",
                "locations": ["Hồ Chí Minh"],
                "salary_min_vnd": 12_000_000,
                "salary_max_vnd": 17_000_000,
                "min_experience": 2,
                "embedding_text": "Job title: Sales Executive B2B",
                "vector_distance": 0.12,
            },
        ),
        FakeSnapshot(
            "wrong-location",
            {
                "job_title": "Sales Executive B2B",
                "company": "ABC",
                "locations": ["Hà Nội"],
                "salary_min_vnd": 12_000_000,
                "salary_max_vnd": 17_000_000,
                "min_experience": 2,
                "vector_distance": 0.14,
            },
        ),
    ]
    embedding_service = FakeEmbeddingService()
    firestore_client = FakeFirestoreClient(snapshots)
    repository = SalaryVectorRepository(
        firestore_client=firestore_client,
        embedding_service=embedding_service,
        vector_collection="data_vector_embeddings",
        stream_timeout=30,
    )

    results = repository.search("Lương Sales B2B ở HCM với 2 năm kinh nghiệm", top_k=5)

    assert firestore_client.collection_name == "data_vector_embeddings"
    assert "Job title: Sales B2B" in embedding_service.last_query_text
    assert len(results) == 1
    assert results[0].record.source_document_id == "match"
    assert results[0].distance == 0.12
    assert results[0].record.salary_min_vnd == 12_000_000

    find_nearest_args = firestore_client.collection_ref.find_nearest_args
    assert find_nearest_args["vector_field"] == "embedding"
    assert find_nearest_args["limit"] == 5
    assert find_nearest_args["distance_result_field"] == "vector_distance"
    assert firestore_client.collection_ref.last_vector_query.stream_timeout == 30
