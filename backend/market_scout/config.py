from dataclasses import dataclass


@dataclass(frozen=True)
class MarketScoutConfig:
    default_location: str = "Vietnam"
    default_currency: str = "VND"
    default_time_horizon: str = "3-5 years"
    max_sources: int = 5
    web_search_enabled: bool = False


DEFAULT_CONFIG = MarketScoutConfig()
