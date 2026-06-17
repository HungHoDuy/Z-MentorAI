from __future__ import annotations

import re
import unicodedata

from backend.market_scout.schemas.salary import SalarySearchQuery


LOCATION_ALIASES = {
    "ho chi minh": "Hồ Chí Minh",
    "hcm": "Hồ Chí Minh",
    "tp hcm": "Hồ Chí Minh",
    "tphcm": "Hồ Chí Minh",
    "tp ho chi minh": "Hồ Chí Minh",
    "sai gon": "Hồ Chí Minh",
    "ha noi": "Hà Nội",
    "hn": "Hà Nội",
    "da nang": "Đà Nẵng",
    "dn": "Đà Nẵng",
    "binh duong": "Bình Dương",
    "dong nai": "Đồng Nai",
    "can tho": "Cần Thơ",
    "hai phong": "Hải Phòng",
}

TITLE_STOPWORDS = {
    "luong",
    "muc",
    "thu",
    "nhap",
    "cua",
    "cho",
    "vi",
    "tri",
    "chuc",
    "danh",
    "nghe",
    "nganh",
    "nhan",
    "vien",
    "kinh",
    "nghiem",
    "nam",
    "bao",
    "nhieu",
    "thang",
}


class SalaryQueryNormalizer:
    """Extract and normalize salary search entities from a user query."""

    def extract(self, query: str) -> SalarySearchQuery:
        location = self.extract_location(query)
        job_title = self.extract_job_title(query)
        experience_years = self.extract_experience_years(query)
        currency = self.extract_currency(query)

        return SalarySearchQuery(
            raw_query=query,
            job_title=job_title,
            job_title_normalized=self.normalize_job_title(job_title) if job_title else None,
            location=location,
            location_normalized=self.normalize_location(location) if location else None,
            experience_years=experience_years,
            currency=currency,
        )

    @classmethod
    def normalize_text(cls, value: str | None) -> str:
        if not value:
            return ""

        text = value.replace("đ", "d").replace("Đ", "D")
        text = unicodedata.normalize("NFD", text)
        text = "".join(char for char in text if unicodedata.category(char) != "Mn")
        text = text.lower()
        text = re.sub(r"[^a-z0-9]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def normalize_job_title(cls, job_title: str | None) -> str:
        normalized = cls.normalize_text(job_title)
        tokens = [token for token in normalized.split() if token not in TITLE_STOPWORDS]
        return " ".join(tokens)

    @classmethod
    def normalize_location(cls, location: str | None) -> str | None:
        normalized = cls.normalize_text(location)
        if not normalized:
            return None
        canonical = LOCATION_ALIASES.get(normalized, location)
        return cls.normalize_text(canonical)

    def extract_location(self, query: str) -> str | None:
        normalized_query = self.normalize_text(query)
        for alias, canonical in sorted(LOCATION_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", normalized_query):
                return canonical
        return None

    def extract_experience_years(self, query: str) -> int | None:
        normalized_query = self.normalize_text(query)
        patterns = (
            r"(?:kinh nghiem|experience)\s*(?:tu|khoang|tren|hon)?\s*(\d{1,2})\s*(?:nam|year|years|yr|yrs)",
            r"(?:tu|khoang|tren|hon|voi|co)?\s*(\d{1,2})\s*(?:nam|year|years|yr|yrs)\s*(?:kinh nghiem|experience)?",
        )

        for pattern in patterns:
            match = re.search(pattern, normalized_query)
            if match:
                return int(match.group(1))
        return None

    @staticmethod
    def extract_currency(query: str) -> str:
        normalized_query = SalaryQueryNormalizer.normalize_text(query)
        if "$" in query or "usd" in normalized_query:
            return "USD"
        return "VND"

    def extract_job_title(self, query: str) -> str | None:
        candidate = query.strip(" ?!.")

        salary_keyword_match = re.search(
            r"(?:lương|mức lương|thu nhập|salary)\s*(?:của|cho|vị trí|chức danh|nghề|ngành)?\s*(.+)",
            candidate,
            flags=re.IGNORECASE,
        )
        if salary_keyword_match:
            candidate = salary_keyword_match.group(1)

        candidate = re.split(
            r"\s+(?:ở|tại|khu vực|với|có|kinh nghiệm|experience)\s+",
            candidate,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]
        candidate = re.sub(
            r"^(?:của|cho|vị trí|chức danh|nghề|ngành|role|position)\s+",
            "",
            candidate.strip(),
            flags=re.IGNORECASE,
        )
        candidate = re.sub(
            r"\b(?:là bao nhiêu|bao nhiêu|khoảng bao nhiêu|một tháng|tháng)\b",
            "",
            candidate,
            flags=re.IGNORECASE,
        )
        candidate = " ".join(candidate.split()).strip(" -,:;")

        if not candidate or self.normalize_job_title(candidate) == "":
            return None
        return candidate

    def title_matches(self, record_title: str, query_title: str | None) -> bool:
        if not query_title:
            return True

        record_tokens = set(self.normalize_job_title(record_title).split())
        query_tokens = set(self.normalize_job_title(query_title).split())
        if not query_tokens:
            return True
        if query_tokens.issubset(record_tokens):
            return True

        overlap = len(record_tokens & query_tokens)
        return overlap / len(query_tokens) >= 0.6

    def location_matches(self, record_locations: list[str], query_location: str | None) -> bool:
        if not query_location:
            return True

        query_normalized = self.normalize_location(query_location)
        if not query_normalized:
            return True

        return any(self.normalize_location(location) == query_normalized for location in record_locations)
