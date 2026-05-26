from __future__ import annotations

import asyncio

from backend.market_scout.crawlers.base_crawler import BaseCrawler
from backend.market_scout.schemas import CrawlResult, CrawlTarget


class SeleniumCrawler(BaseCrawler):
    crawler_type = "selenium"

    def __init__(self, timeout_seconds: int = 25, headless: bool = True) -> None:
        self.timeout_seconds = timeout_seconds
        self.headless = headless

    async def crawl(self, target: CrawlTarget) -> CrawlResult:
        try:
            raw_text = await asyncio.to_thread(self._fetch, target.url)
            document = self.build_document(target=target, raw_text=raw_text, document_type="html")
            return CrawlResult(target=target, document=document)
        except Exception as exc:  # Selenium raises many driver-specific exception types.
            return CrawlResult(target=target, success=False, error=str(exc))

    def _fetch(self, url: str) -> str:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options

        options = Options()
        if self.headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        driver = webdriver.Chrome(options=options)
        try:
            driver.set_page_load_timeout(self.timeout_seconds)
            driver.get(url)
            return driver.page_source
        finally:
            driver.quit()
