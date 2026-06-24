from __future__ import annotations

import re
import unicodedata

from backend.market_scout.schemas.trend_tracker.trend_query import (
    TrendQuery,
    TrendQueryInput,
    TrendQueryIntent,
)
from backend.market_scout.services.trend_tracker.job_category_taxonomy_service import JobCategoryTaxonomyService


INTENT_ALIASES = {
    "current_demand": TrendQueryIntent.CURRENT_DEMAND,
    "hot_trend": TrendQueryIntent.CURRENT_DEMAND,
    "skill_demand": TrendQueryIntent.CURRENT_SKILL_DEMAND,
    "current_skill_demand": TrendQueryIntent.CURRENT_SKILL_DEMAND,
    "displacement_risk": TrendQueryIntent.AUTOMATION_EXPOSURE,
    "automation_exposure": TrendQueryIntent.AUTOMATION_EXPOSURE,
    "external_outlook": TrendQueryIntent.EXTERNAL_OUTLOOK,
    "hiring_outlook": TrendQueryIntent.EXTERNAL_OUTLOOK,
    "supply_gap": TrendQueryIntent.DEMAND_PRESSURE,
    "demand_pressure": TrendQueryIntent.DEMAND_PRESSURE,
}

LOCATION_ALIASES = {
    "hcm": "ho-chi-minh",
    "tp hcm": "ho-chi-minh",
    "tphcm": "ho-chi-minh",
    "tp ho chi minh": "ho-chi-minh",
    "sai gon": "ho-chi-minh",
    "hn": "ha-noi",
    "tp ha noi": "ha-noi",
    "dn": "da-nang",
}


class TrendQueryNormalizer:
    """Resolve query-time category and location input to v2 snapshot dimensions."""

    def __init__(self, *, taxonomy_service: JobCategoryTaxonomyService | None = None) -> None:
        self.taxonomy_service = taxonomy_service or JobCategoryTaxonomyService()
        self.job_family_ids = {
            definition.job_family_id
            for definition in self.taxonomy_service.definitions_by_id.values()
        }

    def normalize(self, query_input: TrendQueryInput) -> TrendQuery:
        intent = self._normalize_intent(query_input.intent)
        category_id, category_family_id = self._resolve_category(
            job_category_id=query_input.job_category_id,
            job_category=query_input.job_category,
        )
        family_id = self._resolve_family(query_input.job_family_id)
        if family_id and category_family_id and family_id != category_family_id:
            raise ValueError(
                "job_family_id does not match the resolved job_category_id."
            )
        resolved_family_id = family_id or category_family_id
        if not resolved_family_id:
            raise ValueError("A job_family_id or job_category_id is required for MVP trend queries.")

        location_id = self._resolve_location(query_input.location_id or query_input.location)
        if not location_id:
            raise ValueError("A location_id or location is required for MVP trend queries.")

        return TrendQuery(
            intent=intent,
            job_family_id=resolved_family_id,
            location_id=location_id,
            job_category_id=category_id,
        )

    def _normalize_intent(self, value: TrendQueryIntent | str) -> TrendQueryIntent:
        if isinstance(value, TrendQueryIntent):
            return value
        raw_value = str(value).strip().casefold()
        intent = INTENT_ALIASES.get(raw_value) or INTENT_ALIASES.get(_text_key(raw_value))
        if not intent:
            supported = ", ".join(intent.value for intent in TrendQueryIntent)
            raise ValueError(f"Unsupported trend intent. Supported values: {supported}.")
        return intent

    def _resolve_category(
        self,
        *,
        job_category_id: str | None,
        job_category: str | None,
    ) -> tuple[str | None, str | None]:
        resolved_from_id = self._definition_for_identifier(job_category_id)
        resolved_from_label = self.taxonomy_service.definition_for_label(job_category or "")
        if resolved_from_id and resolved_from_label:
            if resolved_from_id.job_category_id != resolved_from_label.job_category_id:
                raise ValueError("job_category_id does not match job_category.")

        definition = resolved_from_id or resolved_from_label
        if not definition and (job_category_id or job_category):
            raise ValueError("Unknown job category. Use an ID or raw label defined in JobCategoryTaxonomy.")
        if not definition:
            return None, None
        return definition.job_category_id, definition.job_family_id

    def _resolve_family(self, value: str | None) -> str | None:
        if not value:
            return None
        family_id = _text_key(value).replace(" ", "_") or None
        if family_id not in self.job_family_ids:
            raise ValueError("Unknown job_family_id.")
        return family_id

    def _resolve_location(self, value: str | None) -> str | None:
        key = _text_key(value)
        if not key:
            return None
        return LOCATION_ALIASES.get(key) or _slugify(value)

    def _definition_for_identifier(self, value: str | None):
        if not value:
            return None
        return self.taxonomy_service.definitions_by_id.get(_text_key(value).replace(" ", "_") or None)


def _text_key(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).replace("đ", "d").replace("Đ", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _slugify(value: str | None) -> str | None:
    key = _text_key(value)
    return key.replace(" ", "-") or None
