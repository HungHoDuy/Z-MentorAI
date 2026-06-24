from __future__ import annotations

import asyncio
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.market_scout.crawlers.base_crawler import BaseCrawler
from backend.market_scout.schemas import CrawlResult, CrawlTarget


class RequestsCrawler(BaseCrawler):
    crawler_type = "requests"

    def __init__(self, timeout_seconds: int = 20, user_agent: str | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )

    async def crawl(self, target: CrawlTarget) -> CrawlResult:
        try:
            raw_text, document_type = await asyncio.to_thread(self._fetch, target.url)
            document = self.build_document(target=target, raw_text=raw_text, document_type=document_type)
            return CrawlResult(target=target, document=document)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            return CrawlResult(target=target, success=False, error=str(exc))

    def _fetch(self, url: str) -> tuple[str, str]:
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Connection": "close",
            },
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            content_type = response.headers.get_content_type()
            body = response.read()
            if content_type == "application/pdf" or url.lower().endswith(".pdf"):
                return self._extract_pdf_text(body), "pdf"

            charset = response.headers.get_content_charset() or "utf-8"
            return body.decode(charset, errors="replace"), "html"

    @staticmethod
    def _extract_pdf_text(body: bytes) -> str:
        return f"PDF document fetched successfully. Size: {len(body)} bytes."
