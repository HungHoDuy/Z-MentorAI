from datetime import date

from backend.market_scout.schemas.automation_risk import AutomationExposureSignal
from backend.market_scout.schemas.current_skill_demand import CurrentSkillDemandSignal, SkillFrequency
from backend.market_scout.schemas.job_family_trend_snapshot import JobFamilyTrendSnapshot
from backend.market_scout.schemas.trend_external_evidence import (
    TrendEvidence,
    TrendEvidenceMatch,
    TrendSource,
)
from backend.market_scout.schemas.trend_query import TrendQuery, TrendQueryIntent
from backend.market_scout.schemas.trend_snapshot_read import TrendSnapshotReadResult
from backend.market_scout.services.current_demand_service import CurrentDemandService
from backend.market_scout.services.hybrid_signal_service import HybridSignalService


class FakeSnapshotRepository:
    def __init__(self, result: TrendSnapshotReadResult | None) -> None:
        self.result = result

    def get_latest_for_query(self, query: TrendQuery, *, as_of_date: date | None = None) -> TrendSnapshotReadResult | None:
        return self.result


class FakeSkillFrequencyService:
    def __init__(self) -> None:
        self.called = False

    def evaluate(self, snapshot: JobFamilyTrendSnapshot, *, job_category_id: str | None = None) -> CurrentSkillDemandSignal:
        self.called = True
        return CurrentSkillDemandSignal(
            signal="current_skill_demand",
            job_family_id=snapshot.job_family_id,
            location_id=snapshot.location_id,
            period=snapshot.period,
            sample_size=20,
            skills=[SkillFrequency("excel", 12, 0.6)],
            confidence="low",
            limitations=["Current requirement only."],
        )


class FakeAutomationExposureService:
    def __init__(self) -> None:
        self.called = False

    def evaluate(self, job_category_id: str) -> AutomationExposureSignal:
        self.called = True
        return AutomationExposureSignal(
            signal="automation_exposure",
            job_category_id=job_category_id,
            exposure_level="medium",
            risk_reason="Routine tasks can be assisted.",
            protected_tasks=["Judgment"],
            at_risk_tasks=["Routine entry"],
            confidence="medium",
            source_url="https://example.com/automation",
            limitations=["Global evidence."],
        )


class FakeEvidenceRepository:
    def __init__(self, evidence: list[TrendEvidenceMatch]) -> None:
        self.evidence = evidence
        self.calls = 0

    def list_for_external_outlook(self, **kwargs: object) -> list[TrendEvidenceMatch]:
        self.calls += 1
        return self.evidence


def test_insufficient_internal_sample_stops_all_downstream_signals() -> None:
    skills = FakeSkillFrequencyService()
    automation = FakeAutomationExposureService()
    evidence = FakeEvidenceRepository([_evidence_match()])
    result = _service(_snapshot_read(active_jobs=9, companies=3), skills, automation, evidence).evaluate(_query())

    assert result.signal == "insufficient_evidence"
    assert result.confidence == "low"
    assert not result.directional_trend
    assert not skills.called
    assert not automation.called
    assert evidence.calls == 0


def test_current_demand_is_low_confidence_without_external_evidence() -> None:
    result = _service(
        _snapshot_read(active_jobs=28, companies=19),
        FakeSkillFrequencyService(),
        FakeAutomationExposureService(),
        FakeEvidenceRepository([]),
    ).evaluate(_query())

    assert result.signal == "current_demand_high"
    assert result.confidence == "low"
    assert result.sources == []
    assert not result.directional_trend


def test_current_demand_becomes_medium_confidence_with_matching_external_evidence() -> None:
    result = _service(
        _snapshot_read(active_jobs=28, companies=19),
        FakeSkillFrequencyService(),
        FakeAutomationExposureService(),
        FakeEvidenceRepository([_evidence_match()]),
    ).evaluate(_query())

    assert result.signal == "current_demand_high"
    assert result.confidence == "medium"
    assert result.sources[0]["citation"] == "Page 12"
    assert not result.directional_trend


def test_current_skill_demand_remains_internal_only_low_confidence() -> None:
    skills = FakeSkillFrequencyService()
    result = _service(
        _snapshot_read(active_jobs=28, companies=19),
        skills,
        FakeAutomationExposureService(),
        FakeEvidenceRepository([_evidence_match()]),
    ).evaluate(_query(intent=TrendQueryIntent.CURRENT_SKILL_DEMAND))

    assert result.signal == "current_skill_demand"
    assert result.confidence == "low"
    assert result.sources == []
    assert skills.called


def test_automation_exposure_requires_category_and_returns_task_signal() -> None:
    automation = FakeAutomationExposureService()
    service = _service(
        _snapshot_read(active_jobs=28, companies=19),
        FakeSkillFrequencyService(),
        automation,
        FakeEvidenceRepository([]),
    )

    missing_category = service.evaluate(_query(intent=TrendQueryIntent.AUTOMATION_EXPOSURE, category=None))
    available = service.evaluate(_query(intent=TrendQueryIntent.AUTOMATION_EXPOSURE, category="software_it"))

    assert missing_category.signal == "insufficient_evidence"
    assert available.signal == "automation_exposure"
    assert available.confidence == "medium"
    assert available.data["at_risk_tasks"] == ["Routine entry"]
    assert automation.called


def test_external_outlook_returns_cited_claims_without_directional_internal_trend() -> None:
    result = _service(
        _snapshot_read(active_jobs=28, companies=19),
        FakeSkillFrequencyService(),
        FakeAutomationExposureService(),
        FakeEvidenceRepository([_evidence_match()]),
    ).evaluate(_query(intent=TrendQueryIntent.EXTERNAL_OUTLOOK))

    assert result.signal == "external_outlook"
    assert result.confidence == "medium"
    assert result.data["claims"][0]["exact_claim"] == "A reviewed external outlook claim."
    assert not result.directional_trend


def _service(
    snapshot_read: TrendSnapshotReadResult,
    skills: FakeSkillFrequencyService,
    automation: FakeAutomationExposureService,
    evidence: FakeEvidenceRepository,
) -> HybridSignalService:
    return HybridSignalService(
        snapshot_repository=FakeSnapshotRepository(snapshot_read),
        current_demand_service=CurrentDemandService(),
        skill_frequency_service=skills,
        automation_exposure_service=automation,
        evidence_repository=evidence,
    )


def _query(
    *,
    intent: TrendQueryIntent = TrendQueryIntent.CURRENT_DEMAND,
    category: str | None = "accounting_audit",
) -> TrendQuery:
    return TrendQuery(
        intent=intent,
        job_family_id="finance_legal",
        location_id="ha-noi",
        job_category_id=category,
    )


def _snapshot_read(*, active_jobs: int, companies: int) -> TrendSnapshotReadResult:
    snapshot = JobFamilyTrendSnapshot(
        period="2026-W25",
        period_start=date(2026, 6, 15),
        period_end=date(2026, 6, 21),
        job_family_id="finance_legal",
        location_id="ha-noi",
        observed_job_count=active_jobs + 4,
        active_job_count=active_jobs,
        unknown_active_job_count=0,
        updated_job_count=0,
        distinct_company_count=companies,
        source_job_counts={"careerviet": active_jobs + 4},
        taxonomy_version="job-category-taxonomy-v1",
    )
    return TrendSnapshotReadResult(
        snapshot_id="2026-W25__finance_legal__ha-noi",
        snapshot=snapshot,
        freshness_days=2,
        freshness_status="fresh",
        sample_status="sufficient" if active_jobs >= 10 and companies >= 3 else "insufficient_evidence",
    )


def _evidence_match() -> TrendEvidenceMatch:
    return TrendEvidenceMatch(
        source=TrendSource(
            source_id="report-q2",
            source_name="Reviewed report",
            publisher="Publisher",
            source_type="labor_market_report",
            published_at=date(2026, 6, 10),
            fetched_at=date(2026, 6, 20),
            reliability_score=0.8,
            scope_location_ids=["ha-noi"],
            scope_period="2026-Q2",
            url="https://example.com/report",
            content_hash=None,
            notes=None,
        ),
        evidence=TrendEvidence(
            evidence_id="report-q2-claim-1",
            source_id="report-q2",
            job_family_ids=["finance_legal"],
            job_category_ids=["accounting_audit"],
            location_ids=["ha-noi"],
            period="2026-Q2",
            direction="increase",
            exact_claim="A reviewed external outlook claim.",
            metric_value=18,
            metric_unit="percent_qoq",
            citation="Page 12",
            confidence="medium",
        ),
    )
