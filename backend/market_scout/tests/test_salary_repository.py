from backend.market_scout.repositories.salary_repository import SalaryRepository


class FakeSnapshot:
    def __init__(self, document_id: str, data: dict) -> None:
        self.id = document_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class FakeCollection:
    def __init__(self, documents: list[FakeSnapshot]) -> None:
        self.documents = documents

    def stream(self):
        return iter(self.documents)


class FakeFirestoreClient:
    def __init__(self, documents: list[FakeSnapshot]) -> None:
        self.documents = documents
        self.collection_name = None

    def collection(self, collection_name: str) -> FakeCollection:
        self.collection_name = collection_name
        return FakeCollection(self.documents)


def test_salary_repository_search_records_filters_title_location_experience_and_salary() -> None:
    fake_client = FakeFirestoreClient(
        [
            FakeSnapshot(
                "match",
                {
                    "job_title": "Sales Executive B2B",
                    "company": "ABC",
                    "min_salary": 12,
                    "max_salary": 17,
                    "min_experience": 2,
                    "Địa điểm làm việc": ["Hồ Chí Minh"],
                },
            ),
            FakeSnapshot(
                "too-senior",
                {
                    "job_title": "Sales Executive B2B",
                    "company": "ABC",
                    "min_salary": 20,
                    "max_salary": 30,
                    "min_experience": 5,
                    "Địa điểm làm việc": ["Hồ Chí Minh"],
                },
            ),
            FakeSnapshot(
                "wrong-location",
                {
                    "job_title": "Sales Executive B2B",
                    "company": "ABC",
                    "min_salary": 11,
                    "max_salary": 15,
                    "min_experience": 1,
                    "Địa điểm làm việc": ["Hà Nội"],
                },
            ),
            FakeSnapshot(
                "missing-salary",
                {
                    "job_title": "Sales Executive B2B",
                    "company": "ABC",
                    "min_experience": 1,
                    "Địa điểm làm việc": ["Hồ Chí Minh"],
                },
            ),
        ]
    )
    repository = SalaryRepository(firestore_client=fake_client, collection_name="cleaned_jobs")

    records = repository.search_records("Lương Sales Executive B2B ở HCM với 2 năm kinh nghiệm")

    assert fake_client.collection_name == "cleaned_jobs"
    assert len(records) == 1
    assert records[0].source_document_id == "match"
    assert records[0].salary_min_vnd == 12_000_000
    assert records[0].salary_max_vnd == 17_000_000
