from __future__ import annotations

from backend.market_scout.repositories import CleanedDocumentRepository, RawDocumentRepository
from backend.market_scout.schemas import CleanedDocument, RawDocument
from backend.market_scout.services import TextCleaningService


class CleanDocumentsPipeline:
    def __init__(
        self,
        raw_document_repository: RawDocumentRepository | None = None,
        cleaned_document_repository: CleanedDocumentRepository | None = None,
        text_cleaning_service: TextCleaningService | None = None,
    ) -> None:
        self.raw_document_repository = raw_document_repository or RawDocumentRepository()
        self.cleaned_document_repository = cleaned_document_repository or CleanedDocumentRepository()
        self.text_cleaning_service = text_cleaning_service or TextCleaningService()

    async def run(
        self,
        raw_documents: list[RawDocument] | None = None,
        *,
        save_documents: bool = True,
        overwrite: bool = True,
        deduplicate: bool = True,
    ) -> dict:
        documents = raw_documents if raw_documents is not None else await self.raw_document_repository.load_all()

        cleaned_documents: list[CleanedDocument] = []
        skipped_empty = 0
        skipped_duplicate = 0
        seen_hashes: set[str] = set()

        for raw_document in documents:
            cleaned_document = self.text_cleaning_service.clean(raw_document)
            if cleaned_document is None:
                skipped_empty += 1
                continue

            if deduplicate and cleaned_document.content_hash in seen_hashes:
                skipped_duplicate += 1
                continue

            if cleaned_document.content_hash:
                seen_hashes.add(cleaned_document.content_hash)

            cleaned_documents.append(cleaned_document)

        saved_documents = 0
        if save_documents:
            saved_documents = await self.cleaned_document_repository.save_many(
                cleaned_documents,
                overwrite=overwrite,
            )

        return {
            "status": "success",
            "input_documents": len(documents),
            "cleaned_documents": len(cleaned_documents),
            "saved_documents": saved_documents,
            "skipped_empty": skipped_empty,
            "skipped_duplicate": skipped_duplicate,
            "documents": [document.to_dict() for document in cleaned_documents],
        }
