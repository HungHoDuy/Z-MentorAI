from datetime import date

from backend.market_scout.schemas.trend_tracker.current_skill_demand import CurrentSkillDemandSignal, SkillFrequency
from backend.market_scout.schemas.trend_tracker.job_family_trend_snapshot import JobFamilyTrendSnapshot
from backend.market_scout.schemas.trend_tracker.trend_external_evidence import (
    TrendEvidence,
    TrendEvidenceMatch,
    TrendSource,
)
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery, TrendQueryIntent
from backend.market_scout.schemas.trend_tracker.trend_snapshot_read import TrendSnapshotReadResult
from backend.market_scout.services.trend_tracker.current_demand_service import CurrentDemandService
from backend.market_scout.services.trend_tracker.hybrid_signal_service import HybridSignalService


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


class FakeEvidenceRepository:
    def __init__(self, evidence: list[TrendEvidenceMatch]) -> None:
        self.evidence = evidence
        self.calls = 0

    def list_for_external_outlook(self, **kwargs: object) -> list[TrendEvidenceMatch]:
        self.calls += 1
        return self.evidence


class RaisingEvidenceRepository:
    def list_for_external_outlook(self, **kwargs: object) -> list[TrendEvidenceMatch]:
        raise AssertionError("cached evidence repository should not be called without job_family_id")


class FakeLiveSearchService:
    def __init__(self, evidence: list[TrendEvidenceMatch], *, raises: bool = False) -> None:
        self.evidence = evidence
        self.raises = raises
        self.calls: list[dict[str, object]] = []

    def search(self, user_query: str, query: TrendQuery) -> list[TrendEvidenceMatch]:
        self.calls.append({"user_query": user_query, "query": query})
        if self.raises:
            raise TimeoutError("live search timed out")
        return self.evidence


def test_insufficient_internal_sample_stops_all_downstream_signals() -> None:
    skills = FakeSkillFrequencyService()
    evidence = FakeEvidenceRepository([_evidence_match()])
    result = _service(_snapshot_read(active_jobs=9, companies=3), skills, evidence).evaluate(_query())

    assert result.signal == "insufficient_evidence"
    assert result.confidence == "low"
    assert not result.directional_trend
    assert not skills.called
    assert evidence.calls == 0


def test_current_demand_is_low_confidence_without_external_evidence() -> None:
    result = _service(
        _snapshot_read(active_jobs=28, companies=19),
        FakeSkillFrequencyService(),
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
        FakeEvidenceRepository([_evidence_match()]),
    ).evaluate(_query(intent=TrendQueryIntent.CURRENT_SKILL_DEMAND))

    assert result.signal == "current_skill_demand"
    assert result.confidence == "low"
    assert result.sources == []
    assert skills.called


def test_external_outlook_returns_cited_claims_without_directional_internal_trend() -> None:
    result = _service(
        _snapshot_read(active_jobs=28, companies=19),
        FakeSkillFrequencyService(),
        FakeEvidenceRepository([_evidence_match()]),
    ).evaluate(_query(intent=TrendQueryIntent.EXTERNAL_OUTLOOK))

    assert result.signal == "external_outlook"
    assert result.confidence == "medium"
    assert result.data["claims"][0]["exact_claim"] == "A reviewed external outlook claim."
    assert not result.directional_trend


def test_external_outlook_does_not_require_internal_snapshot() -> None:
    result = _service(
        None,
        FakeSkillFrequencyService(),
        FakeEvidenceRepository([_evidence_match()]),
    ).evaluate(_query(intent=TrendQueryIntent.EXTERNAL_OUTLOOK))

    assert result.signal == "external_outlook"
    assert result.snapshot_id is None
    assert result.data["evidence_count"] == 1
    assert result.sources[0]["url"] == "https://example.com/report"


def test_external_outlook_uses_live_search_when_cache_is_empty() -> None:
    live_search = FakeLiveSearchService([_evidence_match()])
    result = _service(
        None,
        FakeSkillFrequencyService(),
        FakeEvidenceRepository([]),
        live_search=live_search,
    ).evaluate(_query(intent=TrendQueryIntent.EXTERNAL_OUTLOOK), user_query="Sales marketing 2026 outlook")

    assert result.signal == "external_outlook"
    assert result.data["evidence_count"] == 1
    assert live_search.calls[0]["user_query"] == "Sales marketing 2026 outlook"


def test_external_outlook_uses_live_search_when_cached_evidence_is_not_relevant() -> None:
    live_search = FakeLiveSearchService([_evidence_match(claim="Marketing roles need customer and digital skills.")])
    result = _service(
        None,
        FakeSkillFrequencyService(),
        FakeEvidenceRepository([_evidence_match(claim="AI and software skills remain important.")]),
        live_search=live_search,
    ).evaluate(_query(intent=TrendQueryIntent.EXTERNAL_OUTLOOK), user_query="Sales marketing 2026 outlook")

    assert result.signal == "external_outlook"
    assert result.data["claims"][0]["exact_claim"] == "Marketing roles need customer and digital skills."
    assert live_search.calls[0]["user_query"] == "Sales marketing 2026 outlook"

def test_external_outlook_prefers_live_search_before_cached_evidence() -> None:
    live_search = FakeLiveSearchService([_evidence_match(claim="Live search claim.")])
    result = _service(
        None,
        FakeSkillFrequencyService(),
        FakeEvidenceRepository([_evidence_match(claim="Cached claim.")]),
        live_search=live_search,
    ).evaluate(_query(intent=TrendQueryIntent.EXTERNAL_OUTLOOK), user_query="Sales marketing 2026 outlook")

    assert result.signal == "external_outlook"
    assert result.data["claims"][0]["exact_claim"] == "Live search claim."
    assert live_search.calls[0]["user_query"] == "Sales marketing 2026 outlook"


def test_external_outlook_falls_back_to_cached_evidence_when_live_search_is_empty() -> None:
    live_search = FakeLiveSearchService([])
    evidence = FakeEvidenceRepository([_evidence_match(claim="Sales marketing cached outlook.")])
    result = _service(
        None,
        FakeSkillFrequencyService(),
        evidence,
        live_search=live_search,
    ).evaluate(_query(intent=TrendQueryIntent.EXTERNAL_OUTLOOK), user_query="Sales marketing 2026 outlook")

    assert result.signal == "external_outlook"
    assert result.data["claims"][0]["exact_claim"] == "Sales marketing cached outlook."
    assert evidence.calls == 1


def test_external_outlook_falls_back_to_cached_evidence_when_live_search_times_out() -> None:
    live_search = FakeLiveSearchService([], raises=True)
    evidence = FakeEvidenceRepository([_evidence_match(claim="Sales marketing cached outlook.")])
    result = _service(
        None,
        FakeSkillFrequencyService(),
        evidence,
        live_search=live_search,
    ).evaluate(_query(intent=TrendQueryIntent.EXTERNAL_OUTLOOK), user_query="Sales marketing 2026 outlook")

    assert result.signal == "external_outlook"
    assert result.data["claims"][0]["exact_claim"] == "Sales marketing cached outlook."
    assert evidence.calls == 1

def test_external_outlook_without_family_does_not_query_cached_evidence() -> None:
    live_search = FakeLiveSearchService([])
    result = _service(
        None,
        FakeSkillFrequencyService(),
        RaisingEvidenceRepository(),
        live_search=live_search,
    ).evaluate(
        TrendQuery(
            intent=TrendQueryIntent.EXTERNAL_OUTLOOK,
            job_family_id=None,
            location_id="vietnam",
        ),
        user_query="Nhung nganh nghe nao dang co nhu cau tuyen dung cao nhat hien nay?",
    )

    assert result.signal == "insufficient_evidence"
    assert result.confidence == "low"
    assert result.data["evidence_count"] == 0

def _service(
    snapshot_read: TrendSnapshotReadResult | None,
    skills: FakeSkillFrequencyService,
    evidence: FakeEvidenceRepository,
    live_search: FakeLiveSearchService | None = None,
) -> HybridSignalService:
    return HybridSignalService(
        snapshot_repository=FakeSnapshotRepository(snapshot_read),
        current_demand_service=CurrentDemandService(),
        skill_frequency_service=skills,
        evidence_repository=evidence,
        live_search_service=live_search,
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


def _evidence_match(*, claim: str = "A reviewed external outlook claim.") -> TrendEvidenceMatch:
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
            exact_claim=claim,
            metric_value=18,
            metric_unit="percent_qoq",
            citation="Page 12",
            confidence="medium",
        ),
    )









