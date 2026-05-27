from __future__ import annotations

from backend.market_scout.parsers import TrendParser
from backend.market_scout.repositories import CleanedDocumentRepository, TrendRecordRepository
from backend.market_scout.schemas import CleanedDocument, ExtractedTrendRecord


class ExtractTrendPipeline:
    def __init__(
        self,
        cleaned_document_repository: CleanedDocumentRepository | None = None,
        trend_record_repository: TrendRecordRepository | None = None,
        trend_parser: TrendParser | None = None,
    ) -> None:
        self.cleaned_document_repository = cleaned_document_repository or CleanedDocumentRepository()
        self.trend_record_repository = trend_record_repository or TrendRecordRepository()
        self.trend_parser = trend_parser or TrendParser()

    async def run(
        self,
        documents: list[CleanedDocument] | None = None,
        *,
        save_records: bool = True,
        overwrite: bool = True,
    ) -> dict:
        cleaned_documents = documents if documents is not None else await self.cleaned_document_repository.load_all()
        records: list[ExtractedTrendRecord] = []

        for document in cleaned_documents:
            records.extend(self.trend_parser.parse(document))

        saved_records = 0
        if save_records:
            saved_records = await self.trend_record_repository.save_many(records, overwrite=overwrite)

        return {
            "status": "success",
            "input_documents": len(cleaned_documents),
            "trend_records": len(records),
            "saved_records": saved_records,
            "records": [record.to_dict() for record in records],
        }
