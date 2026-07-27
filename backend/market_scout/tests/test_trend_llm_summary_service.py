from backend.market_scout.flows.trend_tracker_flow import TrendTrackerFlowResult
from backend.market_scout.schemas.trend_tracker.hybrid_signal import HybridSignalResult
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery, TrendQueryIntent
from backend.market_scout.services.trend_tracker.trend_llm_summary_service import TrendLlmSummaryService
from backend.market_scout.services.trend_tracker.trend_summary_service import TrendSummaryService


class FakeLlm:
    def __init__(self, response: object | Exception) -> None:
        self.response = response
        self.calls = []

    def invoke(self, messages: object, **kwargs: object) -> object:
        self.calls.append(messages)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_llm_summary_rephrases_answer_but_keeps_deterministic_metadata() -> None:
    llm = FakeLlm("Nhu cau hien tai dang o muc cao, nhung day chua phai trend.")
    result = _result()

    summary = TrendLlmSummaryService(llm=llm).summarize(result)

    assert summary.answer == "Nhu cau hien tai dang o muc cao, nhung day chua phai trend."
    assert summary.confidence == "low"
    assert summary.sources == result.signal.sources
    assert summary.limitations == result.signal.limitations
    assert summary.composer_version == "trend-llm-summary-v1"
    assert llm.calls


def test_llm_failure_returns_deterministic_fallback() -> None:
    result = _result()
    fallback = TrendSummaryService().summarize(result)

    summary = TrendLlmSummaryService(llm=FakeLlm(RuntimeError("model unavailable"))).summarize(result)

    assert summary == fallback



def test_external_outlook_llm_summary_appends_source_links_when_missing() -> None:
    llm = FakeLlm("Blockchain Developer outlook has mixed signals, but current evidence should be checked.")
    result = _external_outlook_result()

    summary = TrendLlmSummaryService(llm=llm).summarize(result)

    assert "Nguon tham khao:" in summary.answer
    assert "[TopDev - Blockchain hiring trends](https://topdev.vn/blockchain-hiring)" in summary.answer
    assert summary.sources == result.signal.sources


def test_external_outlook_llm_summary_does_not_duplicate_source_links() -> None:
    answer = "Blockchain outlook is mixed. Source: https://topdev.vn/blockchain-hiring."
    result = _external_outlook_result()

    summary = TrendLlmSummaryService(llm=FakeLlm(answer)).summarize(result)

    assert summary.answer == answer
def _result() -> TrendTrackerFlowResult:
    query = TrendQuery(
        intent=TrendQueryIntent.CURRENT_DEMAND,
        job_family_id="commercial",
        job_category_id="sales_business",
        location_id="hai-duong",
    )
    return TrendTrackerFlowResult(
        query=query,
        signal=HybridSignalResult(
            intent=query.intent.value,
            signal="current_demand_high",
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id="2026-W25__commercial__hai-duong",
            period="2026-W25",
            confidence="low",
            directional_trend=False,
            data={"active_job_count": 28, "distinct_company_count": 19},
            sources=[{"url": "https://example.com/source"}],
            limitations=["One snapshot is not a trend."],
        ),
    )

def _external_outlook_result() -> TrendTrackerFlowResult:
    query = TrendQuery(
        intent=TrendQueryIntent.EXTERNAL_OUTLOOK,
        job_family_id="digital_telecom",
        job_category_id="software_it",
        location_id="vietnam",
    )
    return TrendTrackerFlowResult(
        query=query,
        signal=HybridSignalResult(
            intent=query.intent.value,
            signal="external_outlook",
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id=None,
            period="2026",
            confidence="medium",
            directional_trend=False,
            data={
                "evidence_count": 1,
                "claims": [
                    {
                        "exact_claim": "Blockchain roles show mixed external outlook signals.",
                        "citation": "Search result snippet",
                    }
                ],
            },
            sources=[
                {
                    "publisher": "TopDev",
                    "source_name": "Blockchain hiring trends",
                    "url": "https://topdev.vn/blockchain-hiring",
                    "citation": "Search result snippet",
                }
            ],
            limitations=["External outlook only."],
        ),
    )
