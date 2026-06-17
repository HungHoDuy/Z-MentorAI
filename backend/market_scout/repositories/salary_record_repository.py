from __future__ import annotations

import json
from pathlib import Path

from backend.market_scout.schemas import ExtractedSalaryRecord, Source


class SalaryRecordRepository:
    def __init__(self, storage_path: str | Path | None = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else self._default_storage_path()

    async def save_many(self, records: list[ExtractedSalaryRecord], *, overwrite: bool = True) -> int:
        if not records:
            return 0

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if overwrite else "a"
        with self.storage_path.open(mode, encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

        return len(records)

    async def load_all(self) -> list[ExtractedSalaryRecord]:
        if not self.storage_path.exists():
            return []

        records: list[ExtractedSalaryRecord] = []
        with self.storage_path.open("r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue
                records.append(self._from_dict(json.loads(line)))

        return records

    @staticmethod
    def _default_storage_path() -> Path:
        return Path(__file__).resolve().parents[1] / "storage" / "salary_records.jsonl"

    @staticmethod
    def _from_dict(data: dict) -> ExtractedSalaryRecord:
        return ExtractedSalaryRecord(
            source=Source(**data["source"]),
            job_title=data["job_title"],
            location=data.get("location"),
            experience_min=data.get("experience_min"),
            experience_max=data.get("experience_max"),
            salary_min=float(data["salary_min"]),
            salary_max=float(data["salary_max"]),
            salary_median=data.get("salary_median"),
            currency=data["currency"],
            period=data.get("period", "monthly"),
            evidence_text=data.get("evidence_text"),
            metadata=data.get("metadata", {}),
        )
