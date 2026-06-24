from datetime import date

from backend.market_scout.flows.trend_tracker_flow import TrendTrackerFlow
from backend.market_scout.schemas.hybrid_signal import HybridSignalResult
from backend.market_scout.schemas.trend_query import TrendQuery, TrendQueryInput, TrendQueryIntent


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
