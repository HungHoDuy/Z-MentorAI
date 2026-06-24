from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.market_scout.repositories.trend_tracker.automation_risk_repository import (
    DEFAULT_AUTOMATION_RISK_COLLECTION,
)
from backend.market_scout.repositories.salary_benchmark.salary_repository import (
    build_firestore_client,
    env_or_default,
    load_env_file,
)
from backend.market_scout.schemas.trend_tracker.automation_risk import AutomationRiskLookup
from backend.market_scout.services.trend_tracker.automation_risk_seed import (
    default_automation_risk_lookups,
)


@dataclass(frozen=True)
class SeedAutomationRiskLookupResult:
    collection_name: str
    records: int
    written_records: int
    dry_run: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": "success",
            "collection_name": self.collection_name,
            "records": self.records,
            "written_records": self.written_records,
            "dry_run": self.dry_run,
        }


class SeedAutomationRiskLookupPipeline:
    """Idempotently persist the reviewed automation-exposure MVP lookup."""

    def __init__(
        self,
        *,
        firestore_client: Any | None = None,
        collection_name: str | None = None,
        lookups: tuple[AutomationRiskLookup, ...] | None = None,
    ) -> None:
        load_env_file()
        self.firestore_client = firestore_client or build_firestore_client()
        self.collection_name = collection_name or env_or_default(
            "MARKET_SCOUT_AUTOMATION_RISK_COLLECTION",
            DEFAULT_AUTOMATION_RISK_COLLECTION,
        )
        self.lookups = lookups or default_automation_risk_lookups()

    def run(self, *, dry_run: bool = False) -> SeedAutomationRiskLookupResult:
        if not dry_run:
            batch = self.firestore_client.batch()
            collection_ref = self.firestore_client.collection(self.collection_name)
            for lookup in self.lookups:
                batch.set(
                    collection_ref.document(lookup.job_category_id),
                    automation_risk_lookup_to_document(lookup),
                    merge=True,
                )
            batch.commit()

        return SeedAutomationRiskLookupResult(
            collection_name=self.collection_name,
            records=len(self.lookups),
            written_records=0 if dry_run else len(self.lookups),
            dry_run=dry_run,
        )


def automation_risk_lookup_to_document(lookup: AutomationRiskLookup) -> dict[str, Any]:
    return {
        "job_category_id": lookup.job_category_id,
        "exposure_level": lookup.exposure_level,
        "risk_reason": lookup.risk_reason,
        "protected_tasks": list(lookup.protected_tasks),
        "at_risk_tasks": list(lookup.at_risk_tasks),
        "source_title": lookup.source_title,
        "source_url": lookup.source_url,
        "published_at": lookup.published_at.isoformat() if lookup.published_at else None,
        "caveat": lookup.caveat,
        "schema_version": 1,
    }
