from backend.market_scout.pipelines.seed_automation_risk_lookup_pipeline import (
    automation_risk_lookup_to_document,
)
from backend.market_scout.services.trend_tracker.automation_risk_seed import (
    default_automation_risk_lookups,
)


def test_default_automation_lookup_has_curated_unique_category_records() -> None:
    lookups = default_automation_risk_lookups()

    assert 10 <= len(lookups) <= 15
    assert len({lookup.job_category_id for lookup in lookups}) == len(lookups)
    assert all(lookup.source_url.startswith("https://") for lookup in lookups)
    assert all(lookup.published_at is not None for lookup in lookups)


def test_automation_lookup_document_includes_required_evidence_fields() -> None:
    document = automation_risk_lookup_to_document(default_automation_risk_lookups()[0])

    assert document["source_url"]
    assert document["published_at"] == "2025-01-07"
    assert document["risk_reason"]
    assert document["protected_tasks"]
    assert document["at_risk_tasks"]
