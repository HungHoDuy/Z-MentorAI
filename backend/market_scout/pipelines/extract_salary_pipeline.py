from __future__ import annotations

from backend.market_scout.parsers import SalaryParser
from backend.market_scout.repositories import CleanedDocumentRepository, SalaryRecordRepository
from backend.market_scout.schemas import CleanedDocument, ExtractedSalaryRecord


class ExtractSalaryPipeline:
    def __init__(
        self,
        cleaned_document_repository: CleanedDocumentRepository | None = None,
        salary_record_repository: SalaryRecordRepository | None = None,
        salary_parser: SalaryParser | None = None,
    ) -> None:
        self.cleaned_document_repository = cleaned_document_repository or CleanedDocumentRepository()
        self.salary_record_repository = salary_record_repository or SalaryRecordRepository()
        self.salary_parser = salary_parser or SalaryParser()

    async def run(
        self,
        documents: list[CleanedDocument] | None = None,
        *,
        save_records: bool = True,
        overwrite: bool = True,
    ) -> dict:
        cleaned_documents = documents if documents is not None else await self.cleaned_document_repository.load_all()
        records: list[ExtractedSalaryRecord] = []

        for document in cleaned_documents:
            records.extend(self.salary_parser.parse(document))

        saved_records = 0
        if save_records:
            saved_records = await self.salary_record_repository.save_many(records, overwrite=overwrite)

        return {
            "status": "success",
            "input_documents": len(cleaned_documents),
            "salary_records": len(records),
            "saved_records": saved_records,
            "records": [record.to_dict() for record in records],
        }
