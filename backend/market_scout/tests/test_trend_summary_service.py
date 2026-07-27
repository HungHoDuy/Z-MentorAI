from backend.market_scout.flows.trend_tracker_flow import TrendTrackerFlowResult
from backend.market_scout.schemas.trend_tracker.hybrid_signal import HybridSignalResult
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQuery, TrendQueryIntent
from backend.market_scout.services.trend_tracker.trend_summary_service import TrendSummaryService


def test_current_demand_summary_keeps_baseline_not_directional_trend() -> None:
    summary = TrendSummaryService().summarize(
        _result(
            signal="current_demand_high",
            data={"active_job_count": 28, "distinct_company_count": 19},
        )
    )

    assert "28 JD active" in summary.answer
    assert "19 công ty" in summary.answer
    assert "không phải kết luận thị trường đang tăng hoặc giảm" in summary.answer
    assert summary.confidence == "low"


def test_external_outlook_summary_only_uses_provided_claim_and_sources() -> None:
    summary = TrendSummaryService().summarize(
        _result(
            signal="external_outlook",
            data={
                "claims": [
                    {
                        "exact_claim": "Technology demand increased in the cited source.",
                        "citation": "Section 2",
                    }
                ]
            },
            sources=[{"url": "https://example.com/report", "citation": "Section 2"}],
            confidence="medium",
        )
    )

    assert "Technology demand increased in the cited source." in summary.answer
    assert summary.sources == [{"url": "https://example.com/report", "citation": "Section 2"}]
    assert summary.confidence == "medium"


def test_insufficient_evidence_summary_surfaces_available_snapshot_metrics() -> None:
    summary = TrendSummaryService().summarize(
        _result(
            signal="insufficient_evidence",
            data={"active_job_count": 3, "distinct_company_count": 2},
        )
    )

    assert "Chưa đủ evidence" in summary.answer
    assert "3 JD active từ 2 công ty" in summary.answer


def _result(
    *,
    signal: str,
    data: dict,
    sources: list[dict] | None = None,
    confidence: str = "low",
) -> TrendTrackerFlowResult:
    query = TrendQuery(
        intent=TrendQueryIntent.CURRENT_DEMAND,
        job_family_id="digital_telecom",
        job_category_id="software_it",
        location_id="ha-noi",
    )
    return TrendTrackerFlowResult(
        query=query,
        signal=HybridSignalResult(
            intent=query.intent.value,
            signal=signal,
            job_family_id=query.job_family_id,
            job_category_id=query.job_category_id,
            location_id=query.location_id,
            snapshot_id="2026-W25__digital_telecom__ha-noi",
            period="2026-W25",
            confidence=confidence,
            directional_trend=False,
            data=data,
            sources=sources or [],
            limitations=["One snapshot is not a trend."],
        ),
    )

