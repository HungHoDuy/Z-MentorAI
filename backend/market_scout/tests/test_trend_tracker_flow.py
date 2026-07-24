from datetime import date

from backend.market_scout.flows.trend_tracker_flow import TrendTrackerFlow
from backend.market_scout.schemas.trend_tracker.hybrid_signal import HybridSignalResult
from backend.market_scout.schemas.trend_tracker.role_fact_match import RoleFactMatch
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery, TrendQueryInput, TrendQueryIntent


class FakeNormalizer:
    def __init__(self, query: TrendQuery) -> None:
        self.query = query
        self.received: TrendQueryInput | None = None

    def normalize(self, query_input: TrendQueryInput) -> TrendQuery:
        self.received = query_input
        return self.query


class FakeHybridSignalService:
    def __init__(self, signal: HybridSignalResult) -> None:
        self.signal = signal
        self.received_query: TrendQuery | None = None
        self.received_as_of_date: date | None = None
        self.received_external_published_after: date | None = None

    def evaluate(
        self,
        query: TrendQuery,
        *,
        as_of_date: date | None = None,
        external_published_after: date | None = None,
    ) -> HybridSignalResult:
        self.received_query = query
        self.received_as_of_date = as_of_date
        self.received_external_published_after = external_published_after
        return self.signal


def test_flow_normalizes_input_then_delegates_to_hybrid_signal_service() -> None:
    query = TrendQuery(
        intent=TrendQueryIntent.CURRENT_DEMAND,
        job_family_id="finance_legal",
        job_category_id="accounting_audit",
        location_id="ha-noi",
    )
    normalizer = FakeNormalizer(query)
    signal_service = FakeHybridSignalService(_signal())
    query_input = TrendQueryInput(
        intent="current_demand",
        job_category="Kế toán / Kiểm toán",
        location="Hà Nội",
    )

    result = TrendTrackerFlow(
        query_normalizer=normalizer,
        hybrid_signal_service=signal_service,
    ).run(
        query_input,
        as_of_date=date(2026, 6, 24),
        external_published_after=date(2025, 7, 1),
    )

    assert normalizer.received == query_input
    assert signal_service.received_query == query
    assert signal_service.received_as_of_date == date(2026, 6, 24)
    assert signal_service.received_external_published_after == date(2025, 7, 1)
    assert result.query == query
    assert result.signal.signal == "current_demand_high"



class FakeRoleSearchService:
    def __init__(self, matches: list[RoleFactMatch]) -> None:
        self.matches = matches
        self.calls: list[dict[str, object]] = []

    def search_for_demand(self, *, role_query: str, location_id: str | None = None, top_k: int = 100, fetch_k: int = 200):
        self.calls.append(
            {
                "role_query": role_query,
                "location_id": location_id,
                "top_k": top_k,
                "fetch_k": fetch_k,
            }
        )
        return self.matches


def test_flow_uses_role_level_current_demand_when_role_mention_exists() -> None:
    query = TrendQuery(
        intent=TrendQueryIntent.CURRENT_DEMAND,
        job_family_id="digital_telecom",
        job_category_id="software_it",
        location_id="ha-noi",
        role_mention="backend engineer",
    )
    normalizer = FakeNormalizer(query)
    signal_service = FakeHybridSignalService(_signal())
    role_search = FakeRoleSearchService(
        [
            _role_match(1, "Company A"),
            _role_match(2, "Company B"),
            _role_match(3, "Company B"),
        ]
    )

    result = TrendTrackerFlow(
        query_normalizer=normalizer,
        hybrid_signal_service=signal_service,
        role_search_service=role_search,
    ).run(TrendQueryInput(intent="current_demand", role_mention="backend engineer", location_id="ha-noi"))

    assert signal_service.received_query is None
    assert role_search.calls == [
        {
            "role_query": "backend engineer",
            "location_id": "ha-noi",
            "top_k": 100,
            "fetch_k": 200,
        }
    ]
    assert result.signal.signal == "current_role_demand_limited"
    assert result.signal.data["role_mention"] == "backend engineer"
    assert result.signal.data["active_job_count"] == 3
    assert len(result.job_sources) == 3


def test_flow_result_exposes_structured_payload_for_summary_layer() -> None:
    query = TrendQuery(
        intent=TrendQueryIntent.EXTERNAL_OUTLOOK,
        job_family_id="digital_telecom",
        job_category_id="software_it",
        location_id="ho-chi-minh",
    )
    result = TrendTrackerFlow(
        query_normalizer=FakeNormalizer(query),
        hybrid_signal_service=FakeHybridSignalService(_signal()),
    ).run(TrendQueryInput(intent=TrendQueryIntent.EXTERNAL_OUTLOOK, job_family_id="digital_telecom", location_id="ho-chi-minh"))

    payload = result.to_dict()

    assert payload["query"]["intent"] == "external_outlook"
    assert payload["signal"]["directional_trend"] is False
    assert payload["signal"]["sources"][0]["url"] == "https://example.com/source"


def _signal() -> HybridSignalResult:
    return HybridSignalResult(
        intent="current_demand",
        signal="current_demand_high",
        job_family_id="finance_legal",
        job_category_id="accounting_audit",
        location_id="ha-noi",
        snapshot_id="2026-W25__finance_legal__ha-noi",
        period="2026-W25",
        confidence="medium",
        directional_trend=False,
        data={"active_job_count": 28, "distinct_company_count": 19},
        sources=[{"url": "https://example.com/source"}],
        limitations=["One internal snapshot is not a trend."],
    )



def _role_match(index: int, company: str) -> RoleFactMatch:
    return RoleFactMatch(
        job_key=f"backend-{index}",
        job_title=f"Backend Developer {index}",
        company=company,
        job_url=f"https://example.com/backend-{index}",
        job_category_ids=["software_it"],
        job_family_ids=["digital_telecom"],
        location_ids=["ha-noi"],
        is_active=True,
        score=0.9 - index * 0.01,
        match_method="semantic",
    )
