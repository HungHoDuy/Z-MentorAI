from __future__ import annotations

import json
from pathlib import Path

from backend.market_scout.schemas import CleanedDocument, Source


class CleanedDocumentRepository:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else self._default_storage_path()

    async def save_many(self, documents: list[CleanedDocument], *, overwrite: bool = True) -> int:
        if not documents:
            return 0

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if overwrite else "a"
        with self.storage_path.open(mode, encoding="utf-8") as file:
            for document in documents:
                file.write(json.dumps(document.to_dict(), ensure_ascii=False) + "\n")

        return len(documents)

    async def load_all(self) -> list[CleanedDocument]:
        if not self.storage_path.exists():
            return []

        documents: list[CleanedDocument] = []
        with self.storage_path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                documents.append(self._from_dict(json.loads(line)))

        return documents

    @staticmethod
    def _default_storage_path() -> Path:
        return Path(__file__).resolve().parents[1] / "storage" / "cleaned_documents.jsonl"

    @staticmethod
    def _from_dict(data: dict) -> CleanedDocument:
        source = Source(**data["source"])
        return CleanedDocument(
            source=source,
            cleaned_text=data.get("cleaned_text", ""),
            sections=data.get("sections", []),
            language=data.get("language", "unknown"),
            document_type=data.get("document_type", "text"),
            content_hash=data.get("content_hash"),
            word_count=data.get("word_count", 0),
            crawled_at=data.get("crawled_at"),
            cleaned_at=data.get("cleaned_at"),
            metadata=data.get("metadata", {}),
        )
