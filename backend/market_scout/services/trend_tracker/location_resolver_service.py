from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from backend.market_scout.schemas.trend_tracker.location_resolution import LocationResolution


DEFAULT_LOCATION_TAXONOMY_FILE = Path(__file__).resolve().parents[2] / "data" / "vietnam_locations.json"


class LocationResolverService:
    """Resolve Vietnamese location mentions to canonical location IDs from a local taxonomy."""

    def __init__(self, *, taxonomy_file: Path | None = None) -> None:
        self.taxonomy_file = taxonomy_file or DEFAULT_LOCATION_TAXONOMY_FILE
        self.locations = _load_locations(self.taxonomy_file)
        self._candidates = _build_candidates(self.locations)

    def resolve(self, value: Any) -> LocationResolution | None:
        key = text_key(value)
        if not key:
            return None

        for phrase, location in self._candidates:
            if contains_text_phrase(key, phrase):
                return LocationResolution(
                    location_id=location["location_id"],
                    canonical_name=location["canonical_name"],
                    matched_text=phrase,
                    confidence="high",
                    resolution_method="local_taxonomy_alias",
                )
        return None


def _load_locations(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("Vietnam location taxonomy must be a JSON list.")

    locations: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        location_id = _optional_text(item.get("location_id"))
        canonical_name = _optional_text(item.get("canonical_name"))
        aliases = item.get("aliases") or []
        if not location_id or not canonical_name:
            continue
        locations.append(
            {
                "location_id": location_id,
                "canonical_name": canonical_name,
                "aliases": [alias for alias in aliases if _optional_text(alias)],
            }
        )
    return locations


def _build_candidates(locations: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    candidates: list[tuple[str, dict[str, Any]]] = []
    seen: set[tuple[str, str]] = set()

    for location in locations:
        aliases = _generated_aliases(location["canonical_name"])
        aliases.extend(str(alias) for alias in location.get("aliases", []))
        aliases.append(location["location_id"].replace("-", " "))

        for alias in aliases:
            phrase = text_key(alias)
            if not phrase:
                continue
            key = (location["location_id"], phrase)
            if key in seen:
                continue
            seen.add(key)
            candidates.append((phrase, location))

    return sorted(candidates, key=lambda item: len(item[0]), reverse=True)


def _generated_aliases(canonical_name: str) -> list[str]:
    base = text_key(canonical_name)
    if not base:
        return []
    aliases = [canonical_name, base, f"tp {base}", f"thanh pho {base}", f"tinh {base}"]
    return aliases


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
