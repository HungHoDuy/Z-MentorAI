from __future__ import annotations

import asyncio

from backend.market_scout.crawlers import CrawlerFactory
from backend.market_scout.data_sources import SourceRegistry
from backend.market_scout.repositories import RawDocumentRepository
from backend.market_scout.schemas import CrawlResult, CrawlTarget, RawDocument


class IngestSourcesPipeline:
    def __init__(
        self,
        source_registry: SourceRegistry | None = None,
        crawler_factory: CrawlerFactory | None = None,
        raw_document_repository: RawDocumentRepository | None = None,
    ) -> None:
        self.source_registry = source_registry or SourceRegistry()
        self.crawler_factory = crawler_factory or CrawlerFactory()
        self.raw_document_repository = raw_document_repository or RawDocumentRepository()

    async def run(
        self,
        targets: list[CrawlTarget] | None = None,
        *,
        save_documents: bool = True,
        concurrency: int = 3,
    ) -> dict:
        crawl_targets = targets or self.source_registry.load()
        semaphore = asyncio.Semaphore(concurrency)

        async def crawl_with_limit(target: CrawlTarget) -> CrawlResult:
            async with semaphore:
                crawler = self.crawler_factory.get(target.crawler_type)
                return await crawler.crawl(target)

        results = await asyncio.gather(*(crawl_with_limit(target) for target in crawl_targets))
        documents = [result.document for result in results if result.success and result.document]

        saved_documents = 0
        if save_documents:
            saved_documents = await self.raw_document_repository.save_many(documents)

        return {
            "status": "success" if all(result.success for result in results) else "partial_success",
            "total_sources": len(crawl_targets),
            "successful_sources": sum(1 for result in results if result.success),
            "failed_sources": sum(1 for result in results if not result.success),
            "saved_documents": saved_documents,
            "documents": [document.to_dict() for document in documents],
            "errors": [
                {"name": result.target.name, "url": result.target.url, "error": result.error}
                for result in results
                if not result.success
            ],
        }

    async def crawl_one(self, target: CrawlTarget, *, save_document: bool = False) -> RawDocument | None:
        result = await self.crawler_factory.get(target.crawler_type).crawl(target)
        if not result.success or not result.document:
            return None

        if save_document:
            await self.raw_document_repository.save_many([result.document])

        return result.document
