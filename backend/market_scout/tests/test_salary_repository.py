from backend.market_scout.repositories.salary_repository import SalaryRepository


class FakeSnapshot:
    def __init__(self, document_id: str, data: dict) -> None:
        self.id = document_id
        self._data = data

    def to_dict(self) -> dict:
        return self._data


class FakeQuery:
    def __init__(
        self,
        documents: list[FakeSnapshot],
        filters: list[tuple[str, str, object]] | None = None,
        limit_count: int | None = None,
    ) -> None:
        self.documents = documents
        self.filters = filters or []
        self.limit_count = limit_count

    def where(self, *args, **kwargs):
        if "filter" in kwargs:
            field_filter = kwargs["filter"]
            field_path = field_filter.field_path
            operator = field_filter.op_string
            value = field_filter.value
        else:
            field_path, operator, value = args

        return FakeQuery(
            self.documents,
            filters=[*self.filters, (field_path, operator, value)],
            limit_count=self.limit_count,
        )

    def limit(self, limit_count: int):
        return FakeQuery(self.documents, filters=self.filters, limit_count=limit_count)

    def stream(self):
        matched = [document for document in self.documents if self._matches_filters(document.to_dict())]
        if self.limit_count is not None:
            matched = matched[: self.limit_count]
        return iter(matched)

    def _matches_filters(self, data: dict) -> bool:
        for field_path, operator, expected in self.filters:
            actual = data.get(field_path)
            if operator == "==" and actual != expected:
                return False
            if operator == ">" and not (actual is not None and actual > expected):
                return False
            if operator == "<=" and not (actual is not None and actual <= expected):
                return False
            if operator == "array_contains" and expected not in (actual or []):
                return False
        return True


class FakeFirestoreClient:
    def __init__(self, documents: list[FakeSnapshot]) -> None:
        self.documents = documents
        self.collection_name = None

    def collection(self, collection_name: str) -> FakeQuery:
        self.collection_name = collection_name
        return FakeQuery(self.documents)


def test_salary_repository_search_records_uses_server_side_title_location_index() -> None:
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
                    "salary_search_keys": ["sales b2b|ho chi minh", "sales executive b2b|ho chi minh"],
                    "job_title_search_keys": ["sales b2b", "sales executive b2b"],
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
                    "salary_search_keys": ["sales b2b|ho chi minh", "sales executive b2b|ho chi minh"],
                    "job_title_search_keys": ["sales b2b", "sales executive b2b"],
                },
            ),
            FakeSnapshot(
                "wrong-title",
                {
                    "job_title": "Marketing Executive",
                    "company": "ABC",
                    "min_salary": 11,
                    "max_salary": 15,
                    "min_experience": 1,
                    "Địa điểm làm việc": ["Hồ Chí Minh"],
                    "salary_search_keys": ["marketing executive|ho chi minh"],
                    "job_title_search_keys": ["marketing executive"],
                },
            ),
        ]
    )
    repository = SalaryRepository(firestore_client=fake_client, collection_name="cleaned_jobs")

    records = repository.search_records("Lương Sales B2B ở HCM với 2 năm kinh nghiệm")

    assert fake_client.collection_name == "cleaned_jobs"
    assert len(records) == 1
    assert records[0].source_document_id == "match"
    assert records[0].salary_min_vnd == 12_000_000
    assert records[0].salary_max_vnd == 17_000_000


def test_salary_repository_builds_server_side_index_filters() -> None:
    fake_client = FakeFirestoreClient([])
    repository = SalaryRepository(firestore_client=fake_client, collection_name="cleaned_jobs")

    query = repository.normalizer.extract("Lương Sales B2B ở HCM với 2 năm kinh nghiệm")
    firestore_query = repository._build_firestore_query(query, require_salary=True, limit=10)

    assert firestore_query.limit_count == 10
    assert ("min_salary", ">", 0) in firestore_query.filters
    assert ("min_experience", "<=", 2) in firestore_query.filters
    assert ("salary_search_keys", "array_contains", "sales b2b|ho chi minh") in firestore_query.filters
    assert not any(field == "Địa điểm làm việc" and operator == "array_contains" for field, operator, _ in firestore_query.filters)
