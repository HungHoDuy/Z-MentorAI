from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from backend.market_scout.schemas.trend_tracker.trend import TrendJobFact


DEFAULT_SOURCE = "careerviet"

JOB_ID_FIELDS = ("job_id", "jobId", "id")
JOB_URL_FIELDS = ("job_url", "jobUrl", "url", "link")
JOB_TITLE_FIELDS = ("job_title", "jobTitle", "title", "T\u00ean c\u00f4ng vi\u1ec7c")
COMPANY_FIELDS = ("company", "company_name", "T\u00ean c\u00f4ng ty")
LOCATION_FIELDS = ("location", "locations", "\u0110\u1ecba \u0111i\u1ec3m l\u00e0m vi\u1ec7c")
INDUSTRY_FIELDS = ("industry", "industries", "Ng\u00e0nh ngh\u1ec1")
SENIORITY_FIELDS = ("seniority", "level", "C\u1ea5p b\u1eadc")
EMPLOYMENT_TYPE_FIELDS = ("employment_type", "employmentType", "H\u00ecnh th\u1ee9c")
UPDATED_AT_FIELDS = ("source_updated_at", "updated_at", "Ng\u00e0y c\u1eadp nh\u1eadt")
EXPIRES_AT_FIELDS = ("source_expires_at", "expires_at", "H\u1ebft h\u1ea1n n\u1ed9p")
REQUIREMENTS_FIELDS = ("requirements", "job_requirements", "Y\u00eau C\u1ea7u C\u00f4ng Vi\u1ec7c")
DESCRIPTION_FIELDS = ("description", "job_description", "M\u00f4 t\u1ea3 C\u00f4ng vi\u1ec7c")

DEFAULT_LOCATION_ALIASES = {
    "ho chi minh": "ho-chi-minh",
    "hcm": "ho-chi-minh",
    "tp hcm": "ho-chi-minh",
    "tphcm": "ho-chi-minh",
    "tp ho chi minh": "ho-chi-minh",
    "ha noi": "ha-noi",
    "hn": "ha-noi",
    "da nang": "da-nang",
}

DEFAULT_INDUSTRY_ALIASES = {
    "quan ly chat luong qa qc": "quality_assurance",
    "qa qc": "quality_assurance",
    "thuc pham do uong": "food_beverage",
    "ke toan kiem toan": "accounting_audit",
    "tai chinh ngan hang": "finance_banking",
}

DEFAULT_SKILL_ALIASES = {
    "haccp": ("haccp",),
    "iso": ("iso",),
    "english": ("tieng anh", "anh ngu", "english"),
    "excel": ("excel",),
    "misa": ("misa",),
    "office_productivity": ("tin hoc van phong",),
    "shift_work": ("lam viec theo ca",),
}


class TrendJobFactNormalizer:
    """Convert a raw job document into deterministic trend dimensions and facts."""

    def __init__(
        self,
        *,
        default_source: str = DEFAULT_SOURCE,
        role_aliases: Mapping[str, str] | None = None,
        industry_aliases: Mapping[str, str] | None = None,
        location_aliases: Mapping[str, str] | None = None,
        skill_aliases: Mapping[str, Iterable[str] | str] | None = None,
    ) -> None:
        self.default_source = _slugify(default_source) or DEFAULT_SOURCE
        self.role_aliases = _normalize_alias_map(role_aliases)
        self.industry_aliases = _normalize_alias_map(DEFAULT_INDUSTRY_ALIASES)
        self.industry_aliases.update(_normalize_alias_map(industry_aliases))
        self.location_aliases = _normalize_alias_map(DEFAULT_LOCATION_ALIASES)
        self.location_aliases.update(_normalize_alias_map(location_aliases))
        self.skill_aliases = _normalize_skill_aliases(DEFAULT_SKILL_ALIASES)
        self.skill_aliases.update(_normalize_skill_aliases(skill_aliases))

    def normalize(
        self,
        document_id: str,
        data: Mapping[str, Any],
        *,
        observed_at: date | datetime | None = None,
    ) -> TrendJobFact | None:
        job_title = _clean_text(_first_value(data, JOB_TITLE_FIELDS))
        if not job_title:
            return None

        source = _slugify(_clean_text(_first_value(data, ("source", "source_name"))) or self.default_source)
        source = source or self.default_source
        source_job_id = _clean_text(_first_value(data, JOB_ID_FIELDS)) or _clean_text(document_id)
        job_url = _clean_text(_first_value(data, JOB_URL_FIELDS))
        canonical_job_url = _canonicalize_url(job_url)
        job_key = _build_job_key(source, source_job_id, canonical_job_url)

        company = _clean_text(_first_value(data, COMPANY_FIELDS))
        requirements_text = _clean_text(_first_value(data, REQUIREMENTS_FIELDS))
        description_text = _clean_text(_first_value(data, DESCRIPTION_FIELDS))
        source_updated_at = _parse_date(_first_value(data, UPDATED_AT_FIELDS))
        source_expires_at = _parse_date(_first_value(data, EXPIRES_AT_FIELDS))
        as_of_date = _as_date(observed_at) or date.today()
        industry_ids = self._industry_ids(_first_value(data, INDUSTRY_FIELDS))
        location_ids = self._location_ids(_first_value(data, LOCATION_FIELDS))

        return TrendJobFact(
            job_key=job_key,
            source=source,
            source_job_id=source_job_id,
            job_url=job_url,
            canonical_job_url=canonical_job_url,
            job_title=job_title,
            role_id=self._role_id(job_title),
            industry_ids=industry_ids,
            location_ids=location_ids,
            company=company,
            company_key=_slugify(company),
            seniority=_slugify(_clean_text(_first_value(data, SENIORITY_FIELDS))),
            employment_type=_slugify(_clean_text(_first_value(data, EMPLOYMENT_TYPE_FIELDS))),
            source_updated_at=source_updated_at,
            source_expires_at=source_expires_at,
            is_active=_is_active(source_expires_at, as_of_date),
            skill_ids=self._skill_ids(requirements_text, description_text),
            content_hash=_content_hash(
                job_title=job_title,
                company=company,
                industries=industry_ids,
                locations=location_ids,
                requirements_text=requirements_text,
                description_text=description_text,
            ),
            requirements_text=requirements_text,
            description_text=description_text,
        )

    def _role_id(self, job_title: str) -> str:
        title_key = _text_key(job_title)
        return self.role_aliases.get(title_key) or _slugify(job_title) or "unknown-role"

    def _industry_ids(self, value: Any) -> list[str]:
        identifiers: list[str] = []
        for industry in _split_industries(value):
            industry_key = _text_key(industry)
            identifier = self.industry_aliases.get(industry_key) or _slugify(industry)
            if identifier:
                identifiers.append(identifier)
        return _deduplicate(identifiers)

    def _location_ids(self, value: Any) -> list[str]:
        identifiers: list[str] = []
        for location in _string_list(value):
            location_key = _text_key(location)
            identifier = self.location_aliases.get(location_key) or _slugify(location)
            if identifier:
                identifiers.append(identifier)
        return _deduplicate(identifiers)

    def _skill_ids(self, requirements_text: str | None, description_text: str | None) -> list[str]:
        searchable_text = _text_key(" ".join(value for value in (requirements_text, description_text) if value))
        if not searchable_text:
            return []

        skill_ids: list[str] = []
        for skill_id, aliases in self.skill_aliases.items():
            if any(_contains_phrase(searchable_text, alias) for alias in aliases):
                skill_ids.append(skill_id)
        return skill_ids


def _normalize_alias_map(aliases: Mapping[str, str] | None) -> dict[str, str]:
    if not aliases:
        return {}
    return {
        _text_key(alias): identifier
        for alias, identifier in aliases.items()
        if _text_key(alias) and identifier
    }


def _normalize_skill_aliases(
    aliases: Mapping[str, Iterable[str] | str] | None,
) -> dict[str, tuple[str, ...]]:
    if not aliases:
        return {}

    normalized: dict[str, tuple[str, ...]] = {}
    for skill_id, values in aliases.items():
        raw_values = (values,) if isinstance(values, str) else tuple(values)
        phrases = tuple(_text_key(value) for value in raw_values if _text_key(value))
        if skill_id and phrases:
            normalized[skill_id] = phrases
    return normalized


def _first_value(data: Mapping[str, Any], field_names: tuple[str, ...]) -> Any:
    for field_name in field_names:
        value = data.get(field_name)
        if value not in (None, ""):
            return value

    normalized_fields = {_text_key(field_name) for field_name in field_names}
    for field_name, value in data.items():
        if _text_key(str(field_name)) in normalized_fields and value not in (None, ""):
            return value
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        value = ", ".join(str(item) for item in value if item not in (None, ""))
    text = " ".join(str(value).split())
    return text or None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return [text for item in values if (text := _clean_text(item))]


def _split_industries(value: Any) -> list[str]:
    industries: list[str] = []
    for raw_value in _string_list(value):
        industries.extend(part.strip() for part in re.split(r"[,;]", raw_value) if part.strip())
    return industries


def _text_key(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).replace("\u0111", "d").replace("\u0110", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _slugify(value: str | None) -> str | None:
    key = _text_key(value)
    return key.replace(" ", "-") or None


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if value is None:
        return None

    text = str(value).strip()
    for pattern in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _as_date(value: date | datetime | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value


def _is_active(source_expires_at: date | None, as_of_date: date) -> bool | None:
    if source_expires_at is None:
        return None
    return source_expires_at >= as_of_date


def _canonicalize_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value.strip())
    if not parsed.scheme or not parsed.netloc:
        return value.strip()

    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), path, "", ""))


def _build_job_key(source: str, source_job_id: str | None, canonical_job_url: str | None) -> str:
    if source_job_id:
        return f"{source}:{source_job_id}"
    if canonical_job_url:
        url_hash = hashlib.sha256(canonical_job_url.encode("utf-8")).hexdigest()[:16]
        return f"{source}:url:{url_hash}"
    raise ValueError("A trend job fact requires a source job id or canonical job URL.")


def _content_hash(
    *,
    job_title: str,
    company: str | None,
    industries: list[str],
    locations: list[str],
    requirements_text: str | None,
    description_text: str | None,
) -> str:
    parts = (
        ("job_title", job_title),
        ("company", company or ""),
        ("industries", "|".join(sorted(industries))),
        ("locations", "|".join(sorted(locations))),
        ("requirements", requirements_text or ""),
        ("description", description_text or ""),
    )
    payload = "\n".join(f"{label}: {value}" for label, value in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None
