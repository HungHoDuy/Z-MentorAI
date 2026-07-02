from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from backend.market_scout.services.trend_tracker.job_category_taxonomy_service import JobCategoryTaxonomyService
from backend.market_scout.services.trend_tracker.location_resolver_service import LocationResolverService
from backend.market_scout.services.trend_tracker.role_fact_search_service import RoleFactSearchService
from backend.market_scout.services.trend_tracker.semantic_role_fact_searcher import SemanticRoleFactSearcher


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


class TrendEntityExtractorService:
    """Extract Trend Tracker query entities from natural-language text and structured hints."""

    def __init__(
        self,
        *,
        taxonomy_service: JobCategoryTaxonomyService | None = None,
        category_aliases: Mapping[str, str] | None = None,
        location_resolver: LocationResolverService | None = None,
        role_search_service: RoleFactSearchService | None = None,
    ) -> None:
        self.taxonomy_service = taxonomy_service or JobCategoryTaxonomyService()
        self.category_aliases = dict(category_aliases or DEFAULT_CATEGORY_ALIASES)
        self.location_resolver = location_resolver or LocationResolverService()
        self.role_search_service = role_search_service
        self.job_family_ids = {
            definition.job_family_id
            for definition in self.taxonomy_service.definitions_by_id.values()
        }

    def extract(self, user_query: str, existing_entities: Mapping[str, Any] | None = None) -> dict[str, str]:
        existing_entities = existing_entities or {}
        extracted: dict[str, str] = {}

        if not _has_any(existing_entities, extracted, ("job_category_id", "job_category", "job_family_id")):
            self._apply_structured_category_or_family_hints(existing_entities, extracted)

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

        if not _has_any(existing_entities, extracted, ("location_id", "location")):
            location_id = self.location_id_from_text(existing_entities.get("location_text") or user_query)
            if location_id:
                extracted["location_id"] = location_id

        if not _has_any(existing_entities, extracted, ("job_category_id", "job_category", "job_family_id")):
            self._apply_role_fact_search(existing_entities, extracted)

        return extracted

    def _apply_structured_category_or_family_hints(
        self,
        existing_entities: Mapping[str, Any],
        extracted: dict[str, str],
    ) -> None:
        category_definition = self.category_definition_from_hint(
            existing_entities.get("job_category_id")
            or existing_entities.get("job_category")
            or existing_entities.get("job_category_hint")
        )
        if category_definition:
            extracted["job_category_id"] = category_definition.job_category_id
            extracted["job_family_id"] = category_definition.job_family_id
            return

        family_id = self.family_id_from_hint(
            existing_entities.get("job_family_id") or existing_entities.get("job_family_hint")
        )
        if family_id:
            extracted["job_family_id"] = family_id

    def _apply_role_fact_search(
        self,
        existing_entities: Mapping[str, Any],
        extracted: dict[str, str],
    ) -> None:
        role_query = _optional_text(existing_entities.get("role_mention") or existing_entities.get("target_role"))
        if not role_query:
            return

        role_search_service = self.role_search_service or RoleFactSearchService(
            semantic_searcher=SemanticRoleFactSearcher(),
        )
        resolution = role_search_service.resolve_role(
            role_query=role_query,
            location_id=_optional_text(existing_entities.get("location_id") or extracted.get("location_id")),
            top_k=5,
        )
        if not resolution.accepted:
            extracted["role_resolution_status"] = "rejected"
            if resolution.rejection_reason:
                extracted["role_resolution_reason"] = resolution.rejection_reason
            return
        if resolution.resolved_job_category_id:
            extracted["resolved_job_category_id"] = resolution.resolved_job_category_id
            extracted["job_category_id"] = resolution.resolved_job_category_id
        if resolution.resolved_job_family_id:
            extracted["resolved_job_family_id"] = resolution.resolved_job_family_id
            extracted["job_family_id"] = resolution.resolved_job_family_id
        extracted["role_resolution_confidence"] = resolution.confidence
        if resolution.matches:
            extracted["role_match_method"] = resolution.matches[0].match_method

    def category_definition_from_hint(self, value: Any):
        key = text_key(value)
        if not key:
            return None
        definition = self.taxonomy_service.definitions_by_id.get(key.replace(" ", "_"))
        if definition:
            return definition
        definition = self.taxonomy_service.definition_for_label(str(value))
        if definition:
            return definition
        alias_category_id = self.category_aliases.get(key)
        if alias_category_id:
            return self.taxonomy_service.definitions_by_id.get(alias_category_id)
        return None

    def family_id_from_hint(self, value: Any) -> str | None:
        key = text_key(value)
        if not key:
            return None
        family_id = key.replace(" ", "_")
        if family_id in self.job_family_ids:
            return family_id
        return None

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

    def location_id_from_text(self, value: Any) -> str | None:
        key = text_key(value)
        if not key:
            return None
        resolution = self.location_resolver.resolve(value)
        if resolution:
            return resolution.location_id
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


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _has_any(
    existing_entities: Mapping[str, Any],
    extracted_entities: Mapping[str, Any],
    keys: tuple[str, ...],
) -> bool:
    return any(existing_entities.get(key) or extracted_entities.get(key) for key in keys)