from __future__ import annotations

from fastapi.testclient import TestClient

from backend.market_scout.main import app, get_market_scout_agent
from backend.market_scout.schemas import MarketScoutIntent, MarketScoutResponse


class FakeAgent:
    def __init__(self) -> None:
        self.requests = []

    async def run(self, request):
        self.requests.append(request)
        return MarketScoutResponse(
            agent="market_scout",
            intent=MarketScoutIntent.TREND_TRACKER,
            answer="ok",
            confidence="low",
        )


def test_scout_accepts_empty_target_role_for_industry_query() -> None:
    fake_agent = FakeAgent()
    app.dependency_overrides[get_market_scout_agent] = lambda: fake_agent
    try:
        client = TestClient(app)
        response = client.post(
            "/scout",
            json={
                "industry": "y te",
                "target_role": "",
                "user_query": "nganh y te job nao dang co nhu cau lon?",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert fake_agent.requests[0].user_query == "nganh y te job nao dang co nhu cau lon?"
    assert fake_agent.requests[0].entities_hint == {"industry": "y te"}
