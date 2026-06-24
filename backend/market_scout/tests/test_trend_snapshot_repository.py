from datetime import date

from backend.market_scout.repositories.trend_snapshot_repository import TrendSnapshotRepository


class FakeSnapshot:
    def __init__(self, document_id: str, data: dict) -> None:
        self.id = document_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class FakeQuery:
    def __init__(self, documents: list[FakeSnapshot]) -> None:
        self.documents = documents
        self.filters: list[tuple[str, str, str]] = []
        self.order_desc = False
        self.limit_count: int | None = None

    def where(self, field_path: str, operator: str, value: str) -> "FakeQuery":
        query = self._copy()
        query.filters.append((field_path, operator, value))
        return query

    def order_by(self, field_path: str, direction: str | None = None) -> "FakeQuery":
        query = self._copy()
        query.order_desc = direction == "DESCENDING"
        return query

    def limit(self, limit_count: int) -> "FakeQuery":
        query = self._copy()
        query.limit_count = limit_count
        return query

    def stream(self, timeout: int | None = None):
        documents = self.documents
        for field_path, _operator, value in self.filters:
            documents = [document for document in documents if document.to_dict().get(field_path) == value]
        documents = sorted(
            documents,
            key=lambda document: document.to_dict().get("period", ""),
            reverse=self.order_desc,
        )
        if self.limit_count is not None:
            documents = documents[: self.limit_count]
        return iter(documents)

    def _copy(self) -> "FakeQuery":
        query = FakeQuery(self.documents)
        query.filters = list(self.filters)
        query.order_desc = self.order_desc
        query.limit_count = self.limit_count
        return query


class FakeFirestoreClient:
    def __init__(self, documents: list[FakeSnapshot]) -> None:
        self.documents = documents

    def collection(self, collection_name: str) -> FakeQuery:
        assert collection_name == "trend_snapshots_v2"
        return FakeQuery(self.documents)


def test_returns_latest_snapshot_with_freshness_and_sample_status() -> None:
    repository = TrendSnapshotRepository(
        firestore_client=FakeFirestoreClient(
            [
                FakeSnapshot("w24", snapshot_document("2026-W24", "2026-06-14", 9, 3)),
                FakeSnapshot("w25", snapshot_document("2026-W25", "2026-06-21", 28, 19)),
            ]
        )
    )

    result = repository.get_latest(
        job_family_id="commercial",
        location_id="hai-duong",
        as_of_date=date(2026, 6, 23),
    )

    assert result is not None
    assert result.snapshot_id == "2026-W25"
    assert result.period == "2026-W25"
    assert result.snapshot.active_job_count == 28
    assert result.freshness_days == 2
    assert result.freshness_status == "fresh"
    assert result.sample_status == "sufficient"


def test_returns_none_when_no_snapshot_matches_dimensions() -> None:
    repository = TrendSnapshotRepository(
        firestore_client=FakeFirestoreClient(
            [FakeSnapshot("w25", snapshot_document("2026-W25", "2026-06-21", 28, 19))]
        )
    )

    assert repository.get_latest(job_family_id="operations", location_id="hai-duong") is None


def test_marks_small_snapshot_as_insufficient_evidence() -> None:
    repository = TrendSnapshotRepository(
        firestore_client=FakeFirestoreClient(
            [FakeSnapshot("w25", snapshot_document("2026-W25", "2026-06-21", 3, 3))]
        )
    )

    result = repository.get_latest(job_family_id="commercial", location_id="hai-duong")

    assert result is not None
    assert result.sample_status == "insufficient_evidence"


def snapshot_document(period: str, period_end: str, active_jobs: int, companies: int) -> dict:
    return {
        "snapshot_id": period,
        "period": period,
        "period_start": "2026-06-08",
        "period_end": period_end,
        "job_family_id": "commercial",
        "location_id": "hai-duong",
        "observed_job_count": active_jobs + 5,
        "active_job_count": active_jobs,
        "unknown_active_job_count": 0,
        "updated_job_count": 0,
        "distinct_company_count": companies,
        "source_job_counts": {"careerviet": active_jobs + 5},
        "taxonomy_version": "job-category-taxonomy-v1",
    }
