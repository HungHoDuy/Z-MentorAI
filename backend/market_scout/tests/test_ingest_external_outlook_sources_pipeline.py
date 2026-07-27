from backend.market_scout.pipelines.trend_tracker.ingest_external_outlook_sources_pipeline import (
    ExternalOutlookSourceConfig,
    IngestExternalOutlookSourcesPipeline,
)


def test_pipeline_dry_run_fetches_allowlisted_sources_without_firestore() -> None:
    result = IngestExternalOutlookSourcesPipeline(
        fetcher=lambda url, timeout: b"report content",
    ).run(source_configs=[_source_config()], dry_run=True)

    assert result.configured_sources == 1
    assert result.fetched_sources == 1
    assert result.changed_sources == 1
    assert result.written_source_records == 0


def test_pipeline_skips_unchanged_source_hash() -> None:
    client = FakeFirestoreClient(existing_hash="sha256:" + "3" * 64)

    result = IngestExternalOutlookSourcesPipeline(
        firestore_client=client,
        fetcher=lambda url, timeout: b"new content",
    ).run(source_configs=[_source_config()], dry_run=False)

    assert result.skipped_unchanged_sources == 0
    assert result.written_source_records == 1
    assert client.written_documents


def test_pipeline_rejects_non_allowlisted_domain() -> None:
    config = _source_config(url="https://malicious.example/report")

    try:
        IngestExternalOutlookSourcesPipeline(fetcher=lambda url, timeout: b"content").run(
            source_configs=[config],
            dry_run=True,
        )
    except ValueError as error:
        assert "not allowlisted" in str(error)
    else:
        raise AssertionError("Expected allowlist validation error.")



def test_pipeline_continues_when_one_source_fetch_fails() -> None:
    configs = [
        _source_config(url="https://example.com/report-a"),
        _source_config(url="https://example.com/report-b"),
    ]
    configs[1] = ExternalOutlookSourceConfig(
        source_id="source-2",
        source_name=configs[1].source_name,
        publisher=configs[1].publisher,
        source_type=configs[1].source_type,
        published_at=configs[1].published_at,
        scope_location_ids=configs[1].scope_location_ids,
        scope_period=configs[1].scope_period,
        url=configs[1].url,
        allowed_domain=configs[1].allowed_domain,
        reliability_score=configs[1].reliability_score,
        topics=configs[1].topics,
    )

    def fetcher(url: str, timeout: int) -> bytes:
        if url.endswith("report-a"):
            raise RuntimeError("403 Forbidden")
        return b"report b"

    result = IngestExternalOutlookSourcesPipeline(fetcher=fetcher).run(
        source_configs=configs,
        dry_run=True,
    )

    assert result.failed_sources == 1
    assert result.changed_sources == 1
    assert result.fetched_sources == 2


def test_pipeline_extracts_and_writes_evidence_when_enabled() -> None:
    client = FakeFirestoreClient()

    result = IngestExternalOutlookSourcesPipeline(
        firestore_client=client,
        fetcher=lambda url, timeout: b"future jobs content",
        evidence_extractor=FakeEvidenceExtractor(),
    ).run(source_configs=[_source_config()], dry_run=False, extract_evidence=True)

    assert result.extracted_evidence_records == 1
    assert result.written_evidence_records == 1
    written_ids = [document_id for document_id, data in client.written_documents]
    assert "evidence-1" in written_ids


def _source_config(url: str = "https://example.com/report") -> ExternalOutlookSourceConfig:
    from datetime import date

    return ExternalOutlookSourceConfig(
        source_id="source-1",
        source_name="Source One",
        publisher="Publisher",
        source_type="labor_market_report",
        published_at=date(2026, 1, 1),
        scope_location_ids=["vietnam"],
        scope_period="2026",
        url=url,
        allowed_domain="example.com",
        reliability_score=0.8,
        topics=["future_jobs"],
    )


class FakeFirestoreClient:
    def __init__(self, existing_hash: str | None = None) -> None:
        self.existing_hash = existing_hash
        self.written_documents: list[tuple[str, dict]] = []

    def collection(self, name: str) -> "FakeCollection":
        return FakeCollection(self)

    def batch(self) -> "FakeBatch":
        return FakeBatch(self)


class FakeCollection:
    def __init__(self, client: FakeFirestoreClient) -> None:
        self.client = client

    def document(self, document_id: str) -> "FakeDocument":
        return FakeDocument(self.client, document_id)


class FakeDocument:
    def __init__(self, client: FakeFirestoreClient, document_id: str) -> None:
        self.client = client
        self.document_id = document_id

    def get(self) -> "FakeSnapshot":
        return FakeSnapshot(self.document_id, self.client.existing_hash)


class FakeSnapshot:
    def __init__(self, document_id: str, content_hash: str | None) -> None:
        self.id = document_id
        self.exists = content_hash is not None
        self.content_hash = content_hash

    def to_dict(self) -> dict:
        return {
            "source_id": self.id,
            "source_name": "Existing source",
            "publisher": "Publisher",
            "source_type": "labor_market_report",
            "published_at": "2026-01-01",
            "fetched_at": "2026-01-02",
            "reliability_score": 0.8,
            "scope_location_ids": ["vietnam"],
            "url": "https://example.com/report",
            "content_hash": self.content_hash,
        }


class FakeBatch:
    def __init__(self, client: FakeFirestoreClient) -> None:
        self.client = client

    def set(self, document: FakeDocument, data: dict, merge: bool = False) -> None:
        self.client.written_documents.append((document.document_id, data))

    def commit(self) -> None:
        return None


class FakeEvidenceExtractor:
    def extract(self, *, source, content_text: str):
        from backend.market_scout.schemas.trend_tracker.trend_external_evidence import TrendEvidence

        return [
            TrendEvidence(
                evidence_id="evidence-1",
                source_id=source.source_id,
                job_family_ids=["digital_telecom"],
                job_category_ids=["software_it"],
                location_ids=["vietnam"],
                period="2026",
                direction="increase",
                exact_claim="AI jobs are mentioned in the source.",
                metric_value=None,
                metric_unit=None,
                citation="Section A",
                confidence="medium",
            )
        ]
