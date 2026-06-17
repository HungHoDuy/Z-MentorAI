from __future__ import annotations

from backend.market_scout.crawlers.base_crawler import BaseCrawler
from backend.market_scout.crawlers.requests_crawler import RequestsCrawler
from backend.market_scout.crawlers.selenium_crawler import SeleniumCrawler


class CrawlerFactory:
    def __init__(self) -> None:
        self._crawlers: dict[str, BaseCrawler] = {
            "requests": RequestsCrawler(),
            "static": RequestsCrawler(),
            "selenium": SeleniumCrawler(),
            "dynamic": SeleniumCrawler(),
        }

    def get(self, crawler_type: str) -> BaseCrawler:
        normalized = crawler_type.strip().lower()
        if normalized not in self._crawlers:
            raise ValueError(f"Unsupported crawler type: {crawler_type}")
        return self._crawlers[normalized]
