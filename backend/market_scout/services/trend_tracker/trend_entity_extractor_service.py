from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from backend.market_scout.services.trend_tracker.job_category_taxonomy_service import JobCategoryTaxonomyService


DEFAULT_CATEGORY_ALIASES: dict[str, str] = {
    "banking": "banking",
    "ngan hang": "banking",
    "nganh ngan hang": "banking",
    "finance banking": "banking",
    "y te": "healthcare_beauty",
    "nganh y te": "healthcare_beauty",
    "healthcare": "healthcare_beauty",
    "cntt": "software_it",
    "cong nghe thong tin": "software_it",
    "it": "software_it",
    "software": "software_it",
    "phan mem": "software_it",
    "sale": "sales_business",
    "sales": "sales_business",
    "ban hang": "sales_business",
    "kinh doanh": "sales_business",
}

DEFAULT_ROLE_CATEGORY_ALIASES: dict[str, str] = {
    "backend engineer": "software_it",
    "backend developer": "software_it",
    "frontend engineer": "software_it",
    "frontend developer": "software_it",
    "software engineer": "software_it",
    "developer": "software_it",
    "lap trinh vien": "software_it",
    "tu van tai chinh": "finance_investment",
    "chuyen vien tu van tai chinh": "finance_investment",
    "nhan vien tin dung": "banking",
    "giao dich vien": "banking",
    "bac si": "healthcare_beauty",
    "dieu duong": "healthcare_beauty",
    "duoc si": "pharmaceuticals_cosmetics",
}

DEFAULT_LOCATION_ALIASES: dict[str, str] = {
    "ha noi": "ha-noi",
    "hn": "ha-noi",
    "hanoi": "ha-noi",
    "ho chi minh": "ho-chi-minh",
    "tp ho chi minh": "ho-chi-minh",
    "hcm": "ho-chi-minh",
    "tphcm": "ho-chi-minh",
    "sai gon": "ho-chi-minh",
    "da nang": "da-nang",
}


class TrendEntityExtractorService:
    """Extract Trend Tracker query entities from natural-language text and legacy hints."""

    def __init__(
        self,
        *,
        taxonomy_service: JobCategoryTaxonomyService | None = None,
        category_aliases: Mapping[str, str] | None = None,
        role_category_aliases: Mapping[str, str] | None = None,
        location_aliases: Mapping[str, str] | None = None,
    ) -> None:
        self.taxonomy_service = taxonomy_service or JobCategoryTaxonomyService()
        self.category_aliases = dict(category_aliases or DEFAULT_CATEGORY_ALIASES)
        self.role_category_aliases = dict(role_category_aliases or DEFAULT_ROLE_CATEGORY_ALIASES)
        self.location_aliases = dict(location_aliases or DEFAULT_LOCATION_ALIASES)
        self.job_family_ids = {
            definition.job_family_id
            for definition in self.taxonomy_service.definitions_by_id.values()
        }

    def extract(self, user_query: str, existing_entities: Mapping[str, Any] | None = None) -> dict[str, str]:
        existing_entities = existing_entities or {}
        extracted: dict[str, str] = {}

        if not _has_any(existing_entities, extracted, ("job_category_id", "job_category", "job_family_id")):
            category_id = self.category_id_from_text(user_query)
            if category_id:
                extracted["job_category_id"] = category_id
            else:
                family_id = self.family_id_from_text(user_query)
                if family_id:
                    extracted["job_family_id"] = family_id

        if not _has_any(existing_entities, extracted, ("job_category_id", "job_category", "job_family_id")):
            category_or_family = self.category_or_family_from_legacy_value(existing_entities.get("industry"))
            if category_or_family in self.job_family_ids:
                extracted["job_family_id"] = category_or_family
            elif category_or_family:
                extracted["job_category_id"] = category_or_family

        if not _has_any(existing_entities, extracted, ("job_category_id", "job_category", "job_family_id")):
            role_category = self.role_category_from_text(existing_entities.get("target_role") or user_query)
            if role_category:
                extracted["job_category_id"] = role_category

        if not _has_any(existing_entities, extracted, ("location_id", "location")):
            location_id = self.location_id_from_text(user_query)
            if location_id:
                extracted["location_id"] = location_id

        return extracted

    def category_id_from_text(self, value: Any) -> str | None:
        key = text_key(value)
        if not key:
            return None

        candidates: list[tuple[str, str]] = []
        for definition in self.taxonomy_service.definitions_by_id.values():
            candidates.append((definition.job_category_id, definition.job_category_id.replace("_", " ")))
            candidates.append((definition.job_category_id, text_key(definition.label)))

        for alias, category_id in self.category_aliases.items():
            candidates.append((category_id, alias))

        for category_id, phrase in sorted(candidates, key=lambda item: len(item[1]), reverse=True):
            if phrase and contains_text_phrase(key, phrase):
                return category_id
        return None

    def family_id_from_text(self, value: Any) -> str | None:
        key = text_key(value)
        if not key:
            return None

        for family_id in sorted(self.job_family_ids, key=len, reverse=True):
            if contains_text_phrase(key, family_id.replace("_", " ")):
                return family_id
        return None

    def category_or_family_from_legacy_value(self, value: Any) -> str | None:
        key = text_key(value)
        if not key:
            return None
        snake_key = key.replace(" ", "_")
        if snake_key in self.job_family_ids:
            return snake_key
        return self.category_aliases.get(key) or snake_key

    def role_category_from_text(self, value: Any) -> str | None:
        key = text_key(value)
        if not key:
            return None
        for alias, category_id in self.role_category_aliases.items():
            if alias in key:
                return category_id
        return None

    def location_id_from_text(self, value: Any) -> str | None:
        key = text_key(value)
        if not key:
            return None
        for alias, location_id in self.location_aliases.items():
            if contains_text_phrase(key, alias):
                return location_id
        return None


def text_key(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace(chr(273), "d").replace(chr(272), "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def contains_text_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def _has_any(
    existing_entities: Mapping[str, Any],
    extracted_entities: Mapping[str, Any],
    keys: tuple[str, ...],
) -> bool:
    return any(existing_entities.get(key) or extracted_entities.get(key) for key in keys)

