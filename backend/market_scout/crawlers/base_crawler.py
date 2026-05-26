from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse

from backend.market_scout.schemas import CrawlResult, CrawlTarget, RawDocument


class TextHTMLParser(HTMLParser):
    SKIPPED_TAGS = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in self.SKIPPED_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIPPED_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            cleaned = " ".join(data.split())
            if cleaned:
                self._chunks.append(cleaned)

    def get_text(self) -> str:
        return "\n".join(self._chunks)


class BaseCrawler(ABC):
    crawler_type: str

    @abstractmethod
    async def crawl(self, target: CrawlTarget) -> CrawlResult:
        raise NotImplementedError

    def build_document(
        self,
        *,
        target: CrawlTarget,
        raw_text: str,
        cleaned_text: str | None = None,
        document_type: str = "html",
        metadata: dict | None = None,
    ) -> RawDocument:
        source = target.to_source()
        return RawDocument(
            source=source,
            raw_text=raw_text,
            cleaned_text=cleaned_text or self.clean_text(raw_text),
            document_type=document_type,
            crawled_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "domain": urlparse(target.url).netloc,
                "crawler_type": self.crawler_type,
                **(metadata or {}),
            },
        )

    @staticmethod
    def clean_text(raw_text: str) -> str:
        parser = TextHTMLParser()
        parser.feed(raw_text)
        text = parser.get_text() or raw_text
        return "\n".join(line.strip() for line in text.splitlines() if line.strip())
