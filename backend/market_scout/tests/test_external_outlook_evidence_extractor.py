from datetime import date

from backend.market_scout.schemas.trend_tracker.trend_external_evidence import TrendSource
from backend.market_scout.services.trend_tracker.external_outlook_evidence_extractor import (
    ExternalOutlookEvidenceExtractor,
)


class FakeLlm:
    def invoke(self, input, **kwargs):
        payload_text = input[1].content
        if '"scope": "commercial"' in payload_text:
            return """[
              {
                "job_family_ids": ["commercial"],
                "job_category_ids": ["sales_business"],
                "location_ids": ["vietnam"],
                "period": "2026",
                "direction": "increase",
                "exact_claim": "Business development and customer-facing roles remain relevant.",
                "metric_value": null,
                "metric_unit": null,
                "citation": "Section: Commercial roles",
                "confidence": "medium"
              }
            ]"""
        return """[
          {
            "job_family_ids": ["digital_telecom"],
            "job_category_ids": ["software_it", "unknown"],
            "location_ids": ["vietnam"],
            "period": "2026",
            "direction": "increase",
            "exact_claim": "AI and software skills remain important for future jobs.",
            "metric_value": null,
            "metric_unit": null,
            "citation": "Section: Future skills",
            "confidence": "medium"
          },
          {
            "job_family_ids": ["outside_scope"],
            "location_ids": ["vietnam"],
            "direction": "increase",
            "exact_claim": "Out of scope claim.",
            "citation": "Other",
            "confidence": "medium"
          }
        ]"""


def test_external_outlook_extractor_returns_only_allowed_scope_claims() -> None:
    evidence = ExternalOutlookEvidenceExtractor(llm=FakeLlm()).extract(
        source=_source(),
        content_text="<html><body>AI and software skills remain important.</body></html>",
    )

    assert len(evidence) == 2
    assert {claim.job_family_ids[0] for claim in evidence} == {"digital_telecom", "commercial"}
    software_claim = next(claim for claim in evidence if claim.job_family_ids == ["digital_telecom"])
    commercial_claim = next(claim for claim in evidence if claim.job_family_ids == ["commercial"])
    assert software_claim.source_id == "source-1"
    assert software_claim.job_category_ids == ["software_it"]
    assert commercial_claim.job_category_ids == ["sales_business"]
    assert software_claim.period == "2026"


def _source() -> TrendSource:
    return TrendSource(
        source_id="source-1",
        source_name="Source One",
        publisher="Publisher",
        source_type="labor_market_report",
        published_at=date(2026, 1, 1),
        fetched_at=date(2026, 1, 2),
        reliability_score=0.8,
        scope_location_ids=["vietnam"],
        scope_period="2026",
        url="https://example.com/report",
        content_hash="sha256:abc",
        notes=None,
    )
