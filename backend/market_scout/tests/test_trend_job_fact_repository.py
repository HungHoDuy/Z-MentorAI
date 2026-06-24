from datetime import date

from backend.market_scout.repositories.trend_tracker.trend_job_fact_repository import TrendJobFactRepository
from backend.market_scout.schemas.trend_tracker.job_family_trend_snapshot import JobFamilyTrendSnapshot


class FakeSnapshot:
    def __init__(self, document_id: str, data: dict) -> None:
        self.id = document_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class FakeQuery:
    def __init__(self, documents: list[FakeSnapshot]) -> None:
        self.documents = documents
        self.filter: tuple[str, str, str] | None = None

    def where(self, field_path: str, operator: str, value: str) -> "FakeQuery":
        query = FakeQuery(self.documents)
        query.filter = (field_path, operator, value)
        return query

    def stream(self, timeout: int | None = None):
        if self.filter is None:
            return iter(self.documents)
        field_path, _operator, value = self.filter
        return iter(
            document
            for document in self.documents
            if value in (document.to_dict().get(field_path) or [])
        )


class FakeFirestoreClient:
    def __init__(self, documents: list[FakeSnapshot]) -> None:
        self.documents = documents

    def collection(self, collection_name: str) -> FakeQuery:
        assert collection_name == "trend_job_facts_v2"
        return FakeQuery(self.documents)


def test_returns_only_active_facts_in_snapshot_cohort_and_deduplicates() -> None:
    repository = TrendJobFactRepository(
        firestore_client=FakeFirestoreClient(
            [
                FakeSnapshot("old", fact_document("job-1", "2026-06-10", "2026-06-30", ["hai-duong"])),
                FakeSnapshot("new", fact_document("job-1", "2026-06-17", "2026-06-30", ["hai-duong"])),
                FakeSnapshot("wrong-location", fact_document("job-2", "2026-06-17", "2026-06-30", ["ha-noi"])),
                FakeSnapshot("expired", fact_document("job-3", "2026-06-17", "2026-06-20", ["hai-duong"])),
                FakeSnapshot("wrong-category", fact_document("job-4", "2026-06-17", "2026-06-30", ["hai-duong"], category_ids=["marketing"])),
            ]
        )
    )

    facts = repository.list_active_for_snapshot(
        make_snapshot(),
        job_category_id="sales_business",
    )

    assert [fact.job_key for fact in facts] == ["careerviet:job-1"]
    assert facts[0].source_updated_at == date(2026, 6, 17)


def test_keeps_multi_location_fact_when_requested_location_matches() -> None:
    repository = TrendJobFactRepository(
        firestore_client=FakeFirestoreClient(
            [
                FakeSnapshot(
                    "multi-location",
                    fact_document("job-1", "2026-06-17", "2026-06-30", ["ha-noi", "hai-duong"]),
                )
            ]
        )
    )

    facts = repository.list_active_for_snapshot(make_snapshot())

    assert len(facts) == 1
    assert facts[0].job_family_ids == ["commercial", "people_services"]


def make_snapshot() -> JobFamilyTrendSnapshot:
    return JobFamilyTrendSnapshot(
        period="2026-W25",
        period_start=date(2026, 6, 15),
        period_end=date(2026, 6, 21),
        job_family_id="commercial",
        location_id="hai-duong",
        observed_job_count=10,
        active_job_count=10,
        unknown_active_job_count=0,
        updated_job_count=0,
        distinct_company_count=3,
        source_job_counts={"careerviet": 10},
        taxonomy_version="job-category-taxonomy-v1",
    )


def fact_document(
    job_id: str,
    updated_at: str,
    expires_at: str,
    location_ids: list[str],
    *,
    category_ids: list[str] | None = None,
) -> dict:
    return {
        "job_key": f"careerviet:{job_id}",
        "source": "careerviet",
        "job_title": "Sales Executive",
        "company": "Example Company",
        "company_key": "example-company",
        "location_ids": location_ids,
        "source_updated_at": updated_at,
        "source_expires_at": expires_at,
        "content_hash": updated_at,
        "requirements_text": "Excel and sales skills",
        "description_text": "Customer development",
        "job_category_ids": category_ids or ["sales_business"],
        "job_family_ids": ["commercial", "people_services"],
        "taxonomy_version": "job-category-taxonomy-v1",
    }
