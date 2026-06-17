from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.market_scout.schemas.salary import SalaryJobRecord, SalarySearchQuery
from backend.market_scout.services.salary_query_normalizer import SalaryQueryNormalizer


DEFAULT_CLEANED_COLLECTION = "cleaned_jobs"
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class SalaryRepository:
    """Firestore repository for salary benchmark records."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        collection_name: str | None = None,
        normalizer: SalaryQueryNormalizer | None = None,
    ) -> None:
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.collection_name = collection_name or env_or_default(
            "MARKET_SCOUT_CLEANED_COLLECTION",
            DEFAULT_CLEANED_COLLECTION,
        )
        self.normalizer = normalizer or SalaryQueryNormalizer()

    def list_records(self, *, limit: int | None = None, require_salary: bool = True) -> list[SalaryJobRecord]:
        records: list[SalaryJobRecord] = []
        query = self.firestore_client.collection(self.collection_name)

        for snapshot in query.stream():
            record = SalaryJobRecord.from_firestore(snapshot.id, snapshot.to_dict() or {})
            if record is None:
                continue
            if require_salary and not record.has_salary:
                continue

            records.append(record)
            if limit is not None and len(records) >= limit:
                break

        return records

    def search_records(
        self,
        query: SalarySearchQuery | str,
        *,
        limit: int | None = None,
        require_salary: bool = True,
    ) -> list[SalaryJobRecord]:
        search_query = self.normalizer.extract(query) if isinstance(query, str) else query

        matched_records: list[SalaryJobRecord] = []
        for record in self.list_records(require_salary=require_salary):
            if not self._matches_query(record, search_query):
                continue

            matched_records.append(record)
            if limit is not None and len(matched_records) >= limit:
                break

        return matched_records

    def _matches_query(self, record: SalaryJobRecord, query: SalarySearchQuery) -> bool:
        if not self.normalizer.title_matches(record.job_title, query.job_title):
            return False

        if not self.normalizer.location_matches(record.locations, query.location):
            return False

        if query.experience_years is not None and record.min_experience is not None:
            if record.min_experience > query.experience_years:
                return False

        return True


def load_env_file(env_file: Path = ENV_FILE) -> None:
    if not env_file.exists():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or key in os.environ:
            continue

        if key == "GOOGLE_APPLICATION_CREDENTIALS":
            credential_path = Path(value)
            if not credential_path.is_absolute():
                credential_path = env_file.parent / credential_path
            value = str(credential_path)

        os.environ[key] = value


def env_or_default(name: str, default: str) -> str:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else default


def build_firestore_client() -> Any:
    try:
        from google.auth.exceptions import DefaultCredentialsError
        from google.cloud import firestore
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency google-cloud-firestore. Install backend/market_scout/requirements.txt first."
        ) from exc

    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if credentials_path and not Path(credentials_path).exists():
        raise RuntimeError(
            "GOOGLE_APPLICATION_CREDENTIALS is set, but the service account JSON file was not found. "
            "Check backend/market_scout/.env."
        )

    try:
        return firestore.Client(
            project=os.getenv("GOOGLE_CLOUD_PROJECT") or None,
            database=os.getenv("MARKET_SCOUT_FIRESTORE_DATABASE") or None,
        )
    except DefaultCredentialsError as exc:
        raise RuntimeError(
            "Firestore credentials were not found. Set GOOGLE_APPLICATION_CREDENTIALS and GOOGLE_CLOUD_PROJECT "
            "in backend/market_scout/.env."
        ) from exc
