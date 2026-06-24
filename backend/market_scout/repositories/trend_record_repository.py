from __future__ import annotations

import json
from pathlib import Path

from backend.market_scout.schemas import ExtractedTrendRecord, Source


class TrendRecordRepository:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else self._default_storage_path()

    async def save_many(self, records: list[ExtractedTrendRecord], *, overwrite: bool = True) -> int:
        if not records:
            return 0

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if overwrite else "a"
        with self.storage_path.open(mode, encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

        return len(records)

    async def load_all(self) -> list[ExtractedTrendRecord]:
        if not self.storage_path.exists():
            return []

        records: list[ExtractedTrendRecord] = []
        with self.storage_path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                records.append(self._from_dict(json.loads(line)))

        return records

    @staticmethod
    def _default_storage_path() -> Path:
        return Path(__file__).resolve().parents[1] / "storage" / "trend_records.jsonl"

    @staticmethod
    def _from_dict(data: dict) -> ExtractedTrendRecord:
        return ExtractedTrendRecord(
            source=Source(**data["source"]),
            market_signal=data["market_signal"],
            trend_type=data.get("trend_type", "growth"),
            industry=data.get("industry"),
            job_title=data.get("job_title"),
            location=data.get("location"),
            time_horizon=data.get("time_horizon"),
            confidence=data.get("confidence", "medium"),
            evidence_text=data.get("evidence_text"),
            metadata=data.get("metadata", {}),
        )
