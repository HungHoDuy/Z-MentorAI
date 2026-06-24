from datetime import date

from backend.market_scout.schemas.trend_tracker.automation_risk import AutomationRiskLookup
from backend.market_scout.services.trend_tracker.automation_exposure_service import AutomationExposureService


class FakeRiskRepository:
    def __init__(self, lookup: AutomationRiskLookup | None) -> None:
        self.lookup = lookup

    def get(self, job_category_id: str) -> AutomationRiskLookup | None:
        return self.lookup if self.lookup and self.lookup.job_category_id == job_category_id else None


def test_returns_curated_task_exposure_without_displacement_prediction() -> None:
    signal = AutomationExposureService(
        risk_repository=FakeRiskRepository(
            AutomationRiskLookup(
                job_category_id="accounting_audit",
                exposure_level="medium",
                risk_reason="Routine reconciliation tasks are more automatable than judgment-heavy audit work.",
                protected_tasks=["Complex audit judgment"],
                at_risk_tasks=["Standard reconciliation"],
                source_title="Verified source",
                source_url="https://example.com/source",
                published_at=date(2025, 1, 1),
                caveat="Global task-exposure evidence requires local validation.",
            )
        )
    ).evaluate("accounting_audit")

    assert signal.signal == "automation_exposure"
    assert signal.exposure_level == "medium"
    assert signal.source_url == "https://example.com/source"
    assert "not a prediction" in signal.limitations[1]


def test_returns_insufficient_evidence_when_lookup_is_missing() -> None:
    signal = AutomationExposureService(risk_repository=FakeRiskRepository(None)).evaluate("software_it")

    assert signal.signal == "insufficient_evidence"
    assert signal.confidence == "low"
