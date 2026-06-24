from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

from backend.market_scout.repositories.salary_repository import (
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.schemas.automation_risk import AutomationRiskLookup


DEFAULT_AUTOMATION_RISK_COLLECTION = "automation_risk_lookup"


class AutomationRiskRepository:
    """Read curated task-exposure lookup records by canonical job category."""

    def __init__(self, *, firestore_client: Any | None = None, collection_name: str | None = None) -> None:
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.collection_name = collection_name or env_or_default(
            "MARKET_SCOUT_AUTOMATION_RISK_COLLECTION",
            DEFAULT_AUTOMATION_RISK_COLLECTION,
        )

    def get(self, job_category_id: str) -> AutomationRiskLookup | None:
        snapshot = self.firestore_client.collection(self.collection_name).document(job_category_id).get()
        if not getattr(snapshot, "exists", False):
            return None
        return automation_risk_from_document(snapshot.to_dict() or {})


def automation_risk_from_document(data: Mapping[str, Any]) -> AutomationRiskLookup | None:
    job_category_id = _text(data.get("job_category_id"))
    exposure_level = _text(data.get("exposure_level"))
    risk_reason = _text(data.get("risk_reason"))
    source_title = _text(data.get("source_title"))
    source_url = _text(data.get("source_url"))
    caveat = _text(data.get("caveat"))
    if not all((job_category_id, exposure_level, risk_reason, source_title, source_url, caveat)):
        return None
    return AutomationRiskLookup(
        job_category_id=job_category_id,
        exposure_level=exposure_level,
        risk_reason=risk_reason,
        protected_tasks=_string_list(data.get("protected_tasks")),
        at_risk_tasks=_string_list(data.get("at_risk_tasks")),
        source_title=source_title,
        source_url=source_url,
        published_at=_to_date(data.get("published_at")),
        caveat=caveat,
    )


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
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None
