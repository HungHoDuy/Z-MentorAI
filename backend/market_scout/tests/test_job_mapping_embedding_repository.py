from __future__ import annotations

from backend.market_scout.repositories.trend_tracker.job_mapping_embedding_repository import (
    JobMappingEmbeddingRepository,
    role_fact_match_from_mapping_document,
)


class FakeSnapshot:
    def __init__(self, document_id: str, data: dict) -> None:
        self.id = document_id
        self._data = data

    def to_dict(self) -> dict:
        return dict(self._data)


class FakeVectorQuery:
    def __init__(self, snapshots: list[FakeSnapshot]) -> None:
        self.snapshots = snapshots
        self.timeout = None

    def stream(self, timeout: int = 60):
        self.timeout = timeout
        return list(self.snapshots)


class FakeCollection:
    def __init__(self, snapshots: list[FakeSnapshot]) -> None:
        self.snapshots = snapshots
        self.find_nearest_kwargs = None

    def find_nearest(self, **kwargs):
        self.find_nearest_kwargs = kwargs
        return FakeVectorQuery(self.snapshots[: kwargs["limit"]])


class FakeFirestoreClient:
    def __init__(self, snapshots: list[FakeSnapshot]) -> None:
        self.collection_name = None
        self.collection_ref = FakeCollection(snapshots)

    def collection(self, name: str) -> FakeCollection:
        self.collection_name = name
        return self.collection_ref


def test_role_fact_match_from_mapping_document_scores_distance_and_location_boost() -> None:
    match = role_fact_match_from_mapping_document(
        "doc-1",
        {
            "job_key": "job-1",
            "job_title": "Backend Developer",
            "job_category_ids": ["software_it"],
            "job_family_ids": ["digital_telecom"],
            "location_ids": ["ha-noi"],
            "vector_distance": 0.2,
        },
        location_id="ha-noi",
    )

    assert match is not None
    assert match.job_key == "job-1"
    assert match.score == 0.9
    assert match.match_method == "semantic"


def test_role_fact_match_filters_location_when_requested() -> None:
    match = role_fact_match_from_mapping_document(
        "doc-1",
        {
            "job_title": "Backend Developer",
            "job_category_ids": ["software_it"],
            "job_family_ids": ["digital_telecom"],
            "location_ids": ["da-nang"],
            "vector_distance": 0.2,
        },
        location_id="ha-noi",
        filter_location=True,
    )

    assert match is None


def test_search_builds_vector_query_and_returns_sorted_matches() -> None:
    firestore_client = FakeFirestoreClient(
        [
            FakeSnapshot(
                "doc-1",
                {
                    "job_key": "backend-hn",
                    "job_title": "Backend Developer",
                    "job_category_ids": ["software_it"],
                    "job_family_ids": ["digital_telecom"],
                    "location_ids": ["ha-noi"],
                    "vector_distance": 0.25,
                },
            ),
            FakeSnapshot(
                "doc-2",
                {
                    "job_key": "backend-dn",
                    "job_title": "Backend Engineer",
                    "job_category_ids": ["software_it"],
                    "job_family_ids": ["digital_telecom"],
                    "location_ids": ["da-nang"],
                    "vector_distance": 0.1,
                },
            ),
        ]
    )
    repository = JobMappingEmbeddingRepository(
        firestore_client=firestore_client,
        embedding_collection="job_mapping_embedding",
        stream_timeout=12,
    )

    matches = repository.search(
        query_embedding=[0.1, 0.2, 0.3],
        location_id="ha-noi",
        top_k=2,
        fetch_k=2,
    )

    assert firestore_client.collection_name == "job_mapping_embedding"
    assert firestore_client.collection_ref.find_nearest_kwargs["vector_field"] == "embedding"
    assert firestore_client.collection_ref.find_nearest_kwargs["limit"] == 2
    assert [match.job_key for match in matches] == ["backend-dn", "backend-hn"]
    assert matches[0].score == 0.9
    assert matches[1].score == 0.85