from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from backend.market_scout.pipelines.trend_tracker.ingest_trend_evidence_pipeline import (
    trend_source_to_document,
)
from backend.market_scout.repositories.salary_benchmark.salary_repository import (
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.repositories.trend_tracker.trend_evidence_repository import (
    DEFAULT_TREND_SOURCE_COLLECTION,
    trend_source_from_document,
)
from backend.market_scout.schemas.trend_tracker.trend_external_evidence import TrendSource


DEFAULT_EXTERNAL_OUTLOOK_CONFIG_PATH = (
    Path(__file__).resolve().parents[2] / "config" / "external_outlook_sources.json"
)
DEFAULT_FETCH_TIMEOUT_SECONDS = 30
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ExternalOutlookSourceConfig:
    source_id: str
    source_name: str
    publisher: str
    source_type: str
    published_at: date
    scope_location_ids: list[str]
    scope_period: str | None
    url: str
    allowed_domain: str
    reliability_score: float
    topics: list[str]


@dataclass(frozen=True)
class ExternalOutlookSourceFetch:
    config: ExternalOutlookSourceConfig
    content_hash: str | None
    content_bytes: int
    changed: bool
    skipped_reason: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class IngestExternalOutlookSourcesResult:
    source_collection: str
    configured_sources: int
    fetched_sources: int
    changed_sources: int
    skipped_unchanged_sources: int
    failed_sources: int
    written_source_records: int
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "success",
            "source_collection": self.source_collection,
            "configured_sources": self.configured_sources,
            "fetched_sources": self.fetched_sources,
            "changed_sources": self.changed_sources,
            "skipped_unchanged_sources": self.skipped_unchanged_sources,
            "failed_sources": self.failed_sources,
            "written_source_records": self.written_source_records,
            "dry_run": self.dry_run,
        }


class IngestExternalOutlookSourcesPipeline:
    """Fetch allowlisted external outlook sources and persist source metadata hashes."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        source_collection: str | None = None,
        fetcher: Callable[[str, int], bytes] | None = None,
        fetch_timeout_seconds: int = DEFAULT_FETCH_TIMEOUT_SECONDS,
    ) -> None:
        load_env_file()
        self.firestore_client = firestore_client
        self.source_collection = source_collection or env_or_default(
            "MARKET_SCOUT_TREND_SOURCE_COLLECTION", DEFAULT_TREND_SOURCE_COLLECTION
        )
        self.fetcher = fetcher or fetch_url_bytes
        self.fetch_timeout_seconds = fetch_timeout_seconds

    def run(
        self,
        *,
        source_configs: list[ExternalOutlookSourceConfig],
        dry_run: bool = False,
    ) -> IngestExternalOutlookSourcesResult:
        if not source_configs:
            raise ValueError("At least one external outlook source must be configured.")

        _validate_unique_sources(source_configs)
        fetched: list[ExternalOutlookSourceFetch] = []
        for config in source_configs:
            _validate_source_url(config)
            try:
                content = self.fetcher(config.url, self.fetch_timeout_seconds)
            except Exception as error:  # noqa: BLE001 - source fetch errors should not fail the whole batch.
                LOGGER.warning("Failed to fetch external outlook source %s: %s", config.source_id, error)
                fetched.append(
                    ExternalOutlookSourceFetch(
                        config=config,
                        content_hash=None,
                        content_bytes=0,
                        changed=False,
                        skipped_reason="fetch_failed",
                        error=str(error),
                    )
                )
                continue
            content_hash = _content_hash(content)
            existing_hash = None if dry_run else self._existing_content_hash(config.source_id)
            changed = dry_run or existing_hash != content_hash
            fetched.append(
                ExternalOutlookSourceFetch(
                    config=config,
                    content_hash=content_hash,
                    content_bytes=len(content),
                    changed=changed,
                    skipped_reason=None if changed else "content_hash_unchanged",
                )
            )

        changed_records = [record for record in fetched if record.changed and record.content_hash]
        if not dry_run and changed_records:
            batch = self._firestore_client().batch()
            collection = self._firestore_client().collection(self.source_collection)
            fetched_at = date.today()
            for record in changed_records:
                source = _to_trend_source(record.config, content_hash=record.content_hash, fetched_at=fetched_at)
                batch.set(collection.document(source.source_id), trend_source_to_document(source), merge=True)
            batch.commit()

        return IngestExternalOutlookSourcesResult(
            source_collection=self.source_collection,
            configured_sources=len(source_configs),
            fetched_sources=len(fetched),
            changed_sources=len(changed_records),
            skipped_unchanged_sources=sum(1 for record in fetched if record.skipped_reason == "content_hash_unchanged"),
            failed_sources=sum(1 for record in fetched if record.skipped_reason == "fetch_failed"),
            written_source_records=0 if dry_run else len(changed_records),
            dry_run=dry_run,
        )

    def _existing_content_hash(self, source_id: str) -> str | None:
        snapshot = self._firestore_client().collection(self.source_collection).document(source_id).get()
        if not getattr(snapshot, "exists", False):
            return None
        source = trend_source_from_document(snapshot.id, snapshot.to_dict() or {})
        return source.content_hash if source is not None else None

    def _firestore_client(self) -> Any:
        if self.firestore_client is None:
            self.firestore_client = build_firestore_client()
        return self.firestore_client


def load_external_outlook_source_configs(path: Path | None = None) -> list[ExternalOutlookSourceConfig]:
    config_path = path or DEFAULT_EXTERNAL_OUTLOOK_CONFIG_PATH
    with config_path.open(encoding="utf-8") as config_file:
        payload = json.load(config_file)
    if not isinstance(payload, list):
        raise ValueError("External outlook source config must be a JSON array.")
    return [_source_config_from_mapping(index, record) for index, record in enumerate(payload)]


def fetch_url_bytes(url: str, timeout_seconds: int) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _source_config_from_mapping(index: int, data: Mapping[str, Any]) -> ExternalOutlookSourceConfig:
    source_id = _text(data.get("source_id"))
    source_name = _text(data.get("source_name"))
    publisher = _text(data.get("publisher"))
    source_type = _text(data.get("source_type"))
    published_at = _to_date(data.get("published_at"))
    scope_location_ids = _string_list(data.get("scope_location_ids"))
    url = _text(data.get("url"))
    allowed_domain = _text(data.get("allowed_domain"))
    reliability_score = _score(data.get("reliability_score"))
    if not all((source_id, source_name, publisher, source_type, published_at, scope_location_ids, url, allowed_domain)):
        raise ValueError(f"Invalid external outlook source config at index {index}.")
    if reliability_score is None:
        raise ValueError(f"Invalid reliability_score at external outlook source config index {index}.")
    return ExternalOutlookSourceConfig(
        source_id=source_id,
        source_name=source_name,
        publisher=publisher,
        source_type=source_type,
        published_at=published_at,
        scope_location_ids=scope_location_ids,
        scope_period=_text(data.get("scope_period")),
        url=url,
        allowed_domain=allowed_domain,
        reliability_score=reliability_score,
        topics=_string_list(data.get("topics")),
    )


def _to_trend_source(
    config: ExternalOutlookSourceConfig,
    *,
    content_hash: str,
    fetched_at: date,
) -> TrendSource:
    notes = "Allowlisted external outlook source. topics=" + ",".join(config.topics)
    return TrendSource(
        source_id=config.source_id,
        source_name=config.source_name,
        publisher=config.publisher,
        source_type=config.source_type,
        published_at=config.published_at,
        fetched_at=fetched_at,
        reliability_score=config.reliability_score,
        scope_location_ids=list(config.scope_location_ids),
        scope_period=config.scope_period,
        url=config.url,
        content_hash=content_hash,
        notes=notes,
    )


def _validate_unique_sources(source_configs: list[ExternalOutlookSourceConfig]) -> None:
    source_ids = [source.source_id for source in source_configs]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Duplicate external outlook source_id values are not allowed.")


def _validate_source_url(config: ExternalOutlookSourceConfig) -> None:
    parsed = urlparse(config.url)
    if parsed.scheme != "https":
        raise ValueError(f"External outlook source must use https: {config.source_id}")
    hostname = parsed.hostname or ""
    allowed = config.allowed_domain.removeprefix("www.")
    normalized_hostname = hostname.removeprefix("www.")
    if normalized_hostname != allowed and not normalized_hostname.endswith(f".{allowed}"):
        raise ValueError(f"External outlook source domain is not allowlisted: {config.source_id}")


def _content_hash(content: bytes) -> str:
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _string_list(value: Any) -> list[str]:
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return list(dict.fromkeys(text for item in values if (text := _text(item))))


def _to_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def _score(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return score if 0 <= score <= 1 else None
