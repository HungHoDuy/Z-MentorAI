import pytest

from backend.market_scout.schemas.trend_query import (
    TrendQueryInput,
    TrendQueryIntent,
)
from backend.market_scout.services.trend_query_normalizer import TrendQueryNormalizer


def test_resolves_raw_category_and_location_to_snapshot_dimensions() -> None:
    query = TrendQueryNormalizer().normalize(
        TrendQueryInput(
            intent="hot_trend",
            job_category="Bán hàng / Kinh doanh",
            location="Hải Dương",
        )
    )

    assert query.intent == TrendQueryIntent.CURRENT_DEMAND
    assert query.job_category_id == "sales_business"
    assert query.job_family_id == "commercial"
    assert query.location_id == "hai-duong"


def test_accepts_canonical_snapshot_dimensions() -> None:
    query = TrendQueryNormalizer().normalize(
        TrendQueryInput(
            intent=TrendQueryIntent.CURRENT_SKILL_DEMAND,
            job_family_id="commercial",
            location_id="hai-duong",
        )
    )

    assert query.job_category_id is None
    assert query.job_family_id == "commercial"
    assert query.location_id == "hai-duong"


def test_rejects_category_family_mismatch() -> None:
    with pytest.raises(ValueError, match="does not match"):
        TrendQueryNormalizer().normalize(
            TrendQueryInput(
                intent="current_demand",
                job_category_id="accounting_audit",
                job_family_id="commercial",
                location_id="ho-chi-minh",
            )
        )
