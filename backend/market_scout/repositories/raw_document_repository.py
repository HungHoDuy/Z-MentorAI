from __future__ import annotations

import json
from pathlib import Path

from backend.market_scout.schemas import RawDocument, Source


class RawDocumentRepository:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else self._default_storage_path()

    async def save_many(self, documents: list[RawDocument]) -> int:
        if not documents:
            return 0

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        with self.storage_path.open("a", encoding="utf-8") as file:
            for document in documents:
                file.write(json.dumps(document.to_dict(), ensure_ascii=False) + "\n")

        return len(documents)

    async def load_all(self) -> list[RawDocument]:
        if not self.storage_path.exists():
            return []

        documents: list[RawDocument] = []
        with self.storage_path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                documents.append(self._from_dict(json.loads(line)))

        return documents

    @staticmethod
    def _default_storage_path() -> Path:
        return Path(__file__).resolve().parents[1] / "storage" / "raw_documents.jsonl"

    @staticmethod
    def _from_dict(data: dict) -> RawDocument:
        source = Source(**data["source"])
        return RawDocument(
            source=source,
            raw_text=data.get("raw_text", ""),
            cleaned_text=data.get("cleaned_text", ""),
            document_type=data.get("document_type", "html"),
            crawled_at=data.get("crawled_at"),
            metadata=data.get("metadata", {}),
        )
