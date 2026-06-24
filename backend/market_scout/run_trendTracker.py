from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.market_scout.agent import MarketScoutAgent
from backend.market_scout.schemas import MarketScoutIntent, MarketScoutRequest
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQueryIntent


def main() -> None:
    args = _parse_args()
    entities = {
        "trend_intent": args.trend_intent,
        "job_family_id": args.job_family_id,
        "job_category_id": args.job_category_id,
        "job_category": args.job_category,
        "location_id": args.location_id,
        "location": args.location,
    }
    request = MarketScoutRequest(
        user_query=args.query or "Trend Tracker structured test request.",
        intent_hint=_market_intent(args.trend_intent),
        entities_hint={key: value for key, value in entities.items() if value is not None},
    )
    response = asyncio.run(MarketScoutAgent().run(request))
    print(json.dumps(response.to_dict(), ensure_ascii=False, indent=2))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one structured Trend Tracker query.")
    parser.add_argument("--trend-intent", choices=[intent.value for intent in TrendQueryIntent], default="current_demand")
    parser.add_argument("--job-family-id", default=None)
    parser.add_argument("--job-category-id", default=None)
    parser.add_argument("--job-category", default=None)
    parser.add_argument("--location-id", default=None)
    parser.add_argument("--location", default=None)
    parser.add_argument("--query", default=None, help="Optional text retained for audit/debug output.")
    return parser.parse_args()


def _market_intent(trend_intent: str) -> MarketScoutIntent:
    if trend_intent == TrendQueryIntent.AUTOMATION_EXPOSURE.value:
        return MarketScoutIntent.INDUSTRY_DECLINE_RISK
    if trend_intent == TrendQueryIntent.EXTERNAL_OUTLOOK.value:
        return MarketScoutIntent.JOB_DEMAND_FORECAST
    return MarketScoutIntent.TREND_TRACKER


if __name__ == "__main__":
    main()
