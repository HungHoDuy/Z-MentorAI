from __future__ import annotations

import re

from backend.market_scout.schemas import CleanedDocument, ExtractedSalaryRecord, SalaryPeriod


class SalaryParser:
    VND_RANGE_PATTERN = re.compile(
        r"(?P<min>\d+(?:[.,]\d+)?)\s*(?:-|–|to|đến)\s*(?P<max>\d+(?:[.,]\d+)?)\s*(?P<unit>triệu|trieu|million)?\s*(?P<currency>vnd|vnđ)?",
        flags=re.IGNORECASE,
    )
    USD_RANGE_PATTERN = re.compile(
        r"\$?\s*(?P<min>\d+(?:[.,]\d+)?)\s*(?:k|K|000)?\s*(?:-|–|to)\s*\$?\s*(?P<max>\d+(?:[.,]\d+)?)\s*(?:k|K|000)?\s*(?:usd|USD)?",
    )
    ROLE_HINT_PATTERN = re.compile(
        r"\b(?P<role>[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+(?:Engineer|Analyst|Manager|Developer|Specialist|Architect|Scientist))\b"
    )

    def parse(self, document: CleanedDocument) -> list[ExtractedSalaryRecord]:
        records: list[ExtractedSalaryRecord] = []
        for section in document.sections:
            if not self._is_salary_section(section):
                continue

            records.extend(self._parse_vnd_ranges(document, section))
            records.extend(self._parse_usd_ranges(document, section))

        return self._deduplicate(records)

    @staticmethod
    def _is_salary_section(text: str) -> bool:
        lowered = text.lower()
        return any(keyword in lowered for keyword in ["salary", "lương", "compensation", "vnd", "vnđ", "usd", "triệu"])

    def _parse_vnd_ranges(self, document: CleanedDocument, section: str) -> list[ExtractedSalaryRecord]:
        records: list[ExtractedSalaryRecord] = []
        for match in self.VND_RANGE_PATTERN.finditer(section):
            unit = (match.group("unit") or "").lower()
            currency = (match.group("currency") or "VND").upper().replace("VNĐ", "VND")
            if currency != "VND" and unit not in {"triệu", "trieu", "million"}:
                continue

            salary_min = self._number(match.group("min"))
            salary_max = self._number(match.group("max"))
            if unit in {"triệu", "trieu", "million"}:
                salary_min *= 1_000_000
                salary_max *= 1_000_000

            records.append(self._build_record(document, section, salary_min, salary_max, "VND"))
        return records

    def _parse_usd_ranges(self, document: CleanedDocument, section: str) -> list[ExtractedSalaryRecord]:
        records: list[ExtractedSalaryRecord] = []
        lowered = section.lower()
        if "$" not in section and "usd" not in lowered:
            return records

        for match in self.USD_RANGE_PATTERN.finditer(section):
            salary_min = self._number(match.group("min"))
            salary_max = self._number(match.group("max"))
            if "k" in match.group(0).lower():
                salary_min *= 1_000
                salary_max *= 1_000
            records.append(self._build_record(document, section, salary_min, salary_max, "USD"))
        return records

    def _build_record(
        self,
        document: CleanedDocument,
        section: str,
        salary_min: float,
        salary_max: float,
        currency: str,
    ) -> ExtractedSalaryRecord:
        salary_min, salary_max = self._normalize_range(salary_min, salary_max)
        return ExtractedSalaryRecord(
            source=document.source,
            job_title=self._extract_job_title(section),
            location=self._extract_location(section),
            salary_min=salary_min,
            salary_max=salary_max,
            currency=currency,
            period=self._extract_period(section),
            evidence_text=section[:1200],
            metadata={
                "parser": "SalaryParser",
                "content_hash": document.content_hash,
                "language": document.language,
            },
        )

    @staticmethod
    def _normalize_range(salary_min: float, salary_max: float) -> tuple[float, float]:
        if salary_min <= salary_max:
            return salary_min, salary_max
        return salary_max, salary_min

    def _extract_job_title(self, section: str) -> str:
        match = self.ROLE_HINT_PATTERN.search(section)
        if match:
            return " ".join(match.group("role").split())
        return "Unknown"

    @staticmethod
    def _extract_location(section: str) -> str | None:
        lowered = section.lower()
        if "vietnam" in lowered or "việt nam" in lowered:
            return "Vietnam"
        if "hanoi" in lowered or "hà nội" in lowered:
            return "Hanoi"
        if "ho chi minh" in lowered or "hcm" in lowered:
            return "Ho Chi Minh City"
        return None

    @staticmethod
    def _extract_period(section: str) -> SalaryPeriod:
        lowered = section.lower()
        if any(keyword in lowered for keyword in ["/year", "per year", "yearly", "annual", "năm"]):
            return SalaryPeriod.YEARLY
        if any(keyword in lowered for keyword in ["/hour", "hourly"]):
            return SalaryPeriod.HOURLY
        return SalaryPeriod.MONTHLY

    @staticmethod
    def _number(raw: str) -> float:
        return float(raw.replace(",", "."))

    @staticmethod
    def _deduplicate(records: list[ExtractedSalaryRecord]) -> list[ExtractedSalaryRecord]:
        seen: set[tuple[str, float, float, str, str]] = set()
        deduped: list[ExtractedSalaryRecord] = []
        for record in records:
            key = (record.job_title, record.salary_min, record.salary_max, record.currency, record.source.url)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)
        return deduped
