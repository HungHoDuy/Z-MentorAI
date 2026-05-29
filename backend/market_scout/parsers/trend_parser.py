from __future__ import annotations

import re

from backend.market_scout.schemas import CleanedDocument, ConfidenceLevel, ExtractedTrendRecord


class TrendParser:
    GROWTH_KEYWORDS = {
        "fastest-growing",
        "fastest growing",
        "jobs on the rise",
        "on the rise",
        "growing",
        "growth",
        "demand",
        "high demand",
        "in-demand",
        "hot",
        "xu hướng",
        "tăng trưởng",
        "nhu cầu",
    }
    DECLINE_KEYWORDS = {
        "decline",
        "declining",
        "automation",
        "automated",
        "obsolete",
        "risk",
        "rủi ro",
        "đào thải",
        "tự động hóa",
    }
    ROLE_PATTERNS = [
        r"\b[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s+(?:Engineer|Analyst|Manager|Developer|Specialist|Architect|Consultant|Scientist)\b",
        r"\b(?:AI|Data|Cloud|Cybersecurity|Machine Learning|Software|DevOps|Product)\s+(?:Engineer|Analyst|Manager|Developer|Specialist|Architect|Scientist)\b",
    ]

    def parse(self, document: CleanedDocument) -> list[ExtractedTrendRecord]:
        records: list[ExtractedTrendRecord] = []

        for section in document.sections:
            normalized = section.lower()
            if not self._is_trend_section(normalized):
                continue

            trend_type = "decline" if self._contains_any(normalized, self.DECLINE_KEYWORDS) else "growth"
            roles = self._extract_roles(section)

            if roles:
                for role in roles:
                    records.append(
                        ExtractedTrendRecord(
                            source=document.source,
                            market_signal=self._summarize_signal(section, role, trend_type),
                            trend_type=trend_type,
                            industry=self._infer_industry(section, role),
                            job_title=role,
                            time_horizon=self._extract_time_horizon(section),
                            confidence=ConfidenceLevel.MEDIUM,
                            evidence_text=section[:1200],
                            metadata={
                                "parser": "TrendParser",
                                "content_hash": document.content_hash,
                                "language": document.language,
                            },
                        )
                    )
            else:
                records.append(
                    ExtractedTrendRecord(
                        source=document.source,
                        market_signal=self._summarize_signal(section, None, trend_type),
                        trend_type=trend_type,
                        industry=self._infer_industry(section, None),
                        time_horizon=self._extract_time_horizon(section),
                        confidence=ConfidenceLevel.LOW,
                        evidence_text=section[:1200],
                        metadata={
                            "parser": "TrendParser",
                            "content_hash": document.content_hash,
                            "language": document.language,
                        },
                    )
                )

        return self._deduplicate(records)

    def _is_trend_section(self, normalized_section: str) -> bool:
        return self._contains_any(normalized_section, self.GROWTH_KEYWORDS | self.DECLINE_KEYWORDS)

    @staticmethod
    def _contains_any(text: str, keywords: set[str]) -> bool:
        return any(keyword in text for keyword in keywords)

    def _extract_roles(self, text: str) -> list[str]:
        roles: list[str] = []
        for pattern in self.ROLE_PATTERNS:
            for match in re.findall(pattern, text):
                role = " ".join(match.split())
                if role not in roles:
                    roles.append(role)
        return roles[:12]

    @staticmethod
    def _extract_time_horizon(text: str) -> str | None:
        year_range = re.search(r"\b(20\d{2})\s*[-–]\s*(20\d{2})\b", text)
        if year_range:
            return f"{year_range.group(1)}-{year_range.group(2)}"

        year = re.search(r"\b(20\d{2})\b", text)
        if year:
            return year.group(1)

        horizon = re.search(r"\b(\d+)\s+(?:years?|năm)\b", text, flags=re.IGNORECASE)
        if horizon:
            return f"{horizon.group(1)} years"

        return None

    @staticmethod
    def _infer_industry(text: str, role: str | None) -> str | None:
        combined = f"{text} {role or ''}".lower()
        if any(keyword in combined for keyword in ["ai", "machine learning", "data"]):
            return "AI/Data"
        if any(keyword in combined for keyword in ["cybersecurity", "security"]):
            return "Cybersecurity"
        if "cloud" in combined or "devops" in combined:
            return "Cloud/DevOps"
        if "product" in combined:
            return "Product"
        return None

    @staticmethod
    def _summarize_signal(section: str, role: str | None, trend_type: str) -> str:
        first_sentence = re.split(r"(?<=[.!?])\s+", section.strip())[0]
        if role:
            return f"{role} shows {trend_type} signal: {first_sentence}"
        return first_sentence[:500]

    @staticmethod
    def _deduplicate(records: list[ExtractedTrendRecord]) -> list[ExtractedTrendRecord]:
        seen: set[tuple[str | None, str, str | None]] = set()
        deduped: list[ExtractedTrendRecord] = []
        for record in records:
            key = (record.job_title, record.trend_type, record.source.url)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)
        return deduped
