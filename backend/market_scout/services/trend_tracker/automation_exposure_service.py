from __future__ import annotations

from backend.market_scout.repositories.trend_tracker.automation_risk_repository import AutomationRiskRepository
from backend.market_scout.schemas.trend_tracker.automation_risk import AutomationExposureSignal


class AutomationExposureService:
    """Return curated task exposure, never a prediction of job displacement."""

    def __init__(self, *, risk_repository: AutomationRiskRepository) -> None:
        self.risk_repository = risk_repository

    def evaluate(self, job_category_id: str) -> AutomationExposureSignal:
        lookup = self.risk_repository.get(job_category_id)
        if lookup is None:
            return AutomationExposureSignal(
                signal="insufficient_evidence",
                job_category_id=job_category_id,
                exposure_level=None,
                risk_reason=None,
                protected_tasks=[],
                at_risk_tasks=[],
                confidence="low",
                source_url=None,
                limitations=["No curated automation-exposure evidence exists for this job category."],
            )
        return AutomationExposureSignal(
            signal="automation_exposure",
            job_category_id=lookup.job_category_id,
            exposure_level=lookup.exposure_level,
            risk_reason=lookup.risk_reason,
            protected_tasks=lookup.protected_tasks,
            at_risk_tasks=lookup.at_risk_tasks,
            confidence="medium",
            source_url=lookup.source_url,
            limitations=[lookup.caveat, "Task exposure is not a prediction that this job will be eliminated."],
        )
