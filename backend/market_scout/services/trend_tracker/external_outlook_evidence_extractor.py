from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from backend.market_scout.schemas.trend_tracker.trend_external_evidence import TrendEvidence, TrendSource


DEFAULT_LLM_MODEL = "gemini-2.5-flash"
DEFAULT_VERTEX_LOCATION = "us-central1"
DEFAULT_MAX_CONTENT_CHARS = 24000
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
SYSTEM_PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts" / "external_outlook_evidence_extraction_system_prompt.txt"
ALLOWED_JOB_FAMILIES = {"digital_telecom", "commercial"}
ALLOWED_JOB_CATEGORIES = {"software_it", "sales_business", "marketing", "digital_marketing", "ecommerce", "customer_service"}
DEFAULT_EXTRACTION_SCOPES = ("it", "commercial")
SCOPE_FAMILY_ALLOWLIST = {
    "it": {"digital_telecom"},
    "commercial": {"commercial"},
}
SCOPE_CATEGORY_ALLOWLIST = {
    "it": {"software_it"},
    "commercial": {"sales_business", "marketing", "digital_marketing", "ecommerce", "customer_service"},
}
ALLOWED_LOCATIONS = {"vietnam", "global"}
ALLOWED_DIRECTIONS = {"increase", "decrease", "mixed", "neutral", "exposure", "skill_shift"}
ALLOWED_CONFIDENCE = {"high", "medium", "low"}


class ChatModel(Protocol):
    def invoke(self, input: Any, **kwargs: Any) -> Any:
        ...


class ExternalOutlookEvidenceExtractor:
    """Extract structured external outlook claims from allowlisted source text."""

    def __init__(
        self,
        *,
        llm: ChatModel | None = None,
        model_name: str | None = None,
        project: str | None = None,
        location: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 2048,
        max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
    ) -> None:
        _load_env_file()
        self._llm = llm
        self.model_name = model_name or os.getenv("MARKET_SCOUT_EXTERNAL_OUTLOOK_EXTRACTION_MODEL", DEFAULT_LLM_MODEL)
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.getenv("MARKET_SCOUT_VERTEX_LOCATION", DEFAULT_VERTEX_LOCATION)
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.max_content_chars = max_content_chars

    def extract(
        self,
        *,
        source: TrendSource,
        content_text: str,
        scopes: tuple[str, ...] = DEFAULT_EXTRACTION_SCOPES,
    ) -> list[TrendEvidence]:
        cleaned_text = _normalize_content(content_text)[: self.max_content_chars]
        if not cleaned_text:
            return []

        evidence_by_id: dict[str, TrendEvidence] = {}
        for scope in scopes:
            if scope not in SCOPE_FAMILY_ALLOWLIST:
                continue
            response = (self._llm or self._build_llm()).invoke(
                [
                    SystemMessage(content=_load_system_prompt()),
                    HumanMessage(
                        content=json.dumps(
                            {
                                "extraction_scope": _scope_instruction(scope),
                                "source": {
                                    "source_id": source.source_id,
                                    "source_name": source.source_name,
                                    "publisher": source.publisher,
                                    "url": source.url,
                                    "published_at": source.published_at.isoformat(),
                                    "scope_location_ids": source.scope_location_ids,
                                    "scope_period": source.scope_period,
                                },
                                "content_text": cleaned_text,
                            },
                            ensure_ascii=False,
                        )
                    ),
                ]
            )
            payload = _parse_json_array(_response_to_text(response))
            for index, item in enumerate(payload):
                if not isinstance(item, Mapping):
                    continue
                claim = _trend_evidence_from_payload(source, index, item, scope=scope)
                if claim is not None:
                    evidence_by_id[claim.evidence_id] = claim
        return list(evidence_by_id.values())

    def _build_llm(self) -> ChatModel:
        try:
            from langchain_google_vertexai import ChatVertexAI
        except ImportError as exc:
            raise RuntimeError("Missing dependency langchain-google-vertexai.") from exc
        return ChatVertexAI(
            model=self.model_name,
            project=self.project,
            location=self.location,
            temperature=self.temperature,
            max_tokens=self.max_output_tokens,
            thinking_budget=0,
            max_retries=1,
        )


def _trend_evidence_from_payload(
    source: TrendSource,
    index: int,
    payload: Mapping[str, Any],
    *,
    scope: str,
) -> TrendEvidence | None:
    job_family_ids = _filtered_list(payload.get("job_family_ids"), SCOPE_FAMILY_ALLOWLIST[scope])
    job_category_ids = _filtered_list(payload.get("job_category_ids"), SCOPE_CATEGORY_ALLOWLIST[scope])
    location_ids = _filtered_list(payload.get("location_ids"), ALLOWED_LOCATIONS)
    direction = _optional_text(payload.get("direction")) or "neutral"
    exact_claim = _optional_text(payload.get("exact_claim"))
    citation = _optional_text(payload.get("citation")) or source.source_name
    confidence = _optional_text(payload.get("confidence")) or "low"

    if not job_family_ids or not location_ids or not exact_claim:
        return None
    if direction not in ALLOWED_DIRECTIONS:
        direction = "neutral"
    if confidence not in ALLOWED_CONFIDENCE:
        confidence = "low"

    return TrendEvidence(
        evidence_id=_evidence_id(source.source_id, scope, _optional_text(payload.get("period")), exact_claim, index),
        source_id=source.source_id,
        job_family_ids=job_family_ids,
        job_category_ids=job_category_ids,
        location_ids=location_ids,
        period=_optional_text(payload.get("period")),
        direction=direction,
        exact_claim=exact_claim,
        metric_value=_number(payload.get("metric_value")),
        metric_unit=_optional_text(payload.get("metric_unit")),
        citation=citation,
        confidence=confidence,
    )


def _evidence_id(source_id: str, scope: str, period: str | None, exact_claim: str, index: int) -> str:
    digest = hashlib.sha256(exact_claim.casefold().encode("utf-8")).hexdigest()[:16]
    period_key = re.sub(r"[^a-zA-Z0-9]+", "-", period or "unknown").strip("-").casefold() or "unknown"
    return f"{source_id}__{scope}__{period_key}__{index:02d}__{digest}"


def _scope_instruction(scope: str) -> dict[str, Any]:
    if scope == "commercial":
        return {
            "scope": "commercial",
            "job_family_ids": ["commercial"],
            "job_category_ids": ["sales_business", "marketing", "digital_marketing", "ecommerce", "customer_service"],
            "look_for": [
                "sales",
                "business development",
                "account management",
                "customer service",
                "customer experience",
                "marketing",
                "digital marketing",
                "ecommerce",
                "retail sales",
                "commercial operations",
                "consumer business",
            ],
        }
    return {
        "scope": "it",
        "job_family_ids": ["digital_telecom"],
        "job_category_ids": ["software_it"],
        "look_for": ["software", "IT", "AI", "data", "cybersecurity", "cloud", "digital technology"],
    }


def _normalize_content(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _parse_json_array(text: str) -> list[Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    if isinstance(data, dict):
        data = data.get("evidence", [])
    if not isinstance(data, list):
        raise ValueError("Expected a JSON array from external outlook extraction LLM.")
    return data


def _filtered_list(value: Any, allowed_values: set[str]) -> list[str]:
    values = value if isinstance(value, (list, tuple, set)) else [value]
    result: list[str] = []
    for item in values:
        text = _optional_text(item)
        if text in allowed_values and text not in result:
            result.append(text)
    return result


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text or text.casefold() == "null":
        return None
    return text


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _response_to_text(response: Any) -> str:
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content)


def _load_system_prompt(prompt_file: Path = SYSTEM_PROMPT_FILE) -> str:
    return prompt_file.read_text(encoding="utf-8")


def _load_env_file(env_file: Path = ENV_FILE) -> None:
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key or key in os.environ:
            continue
        if key == "GOOGLE_APPLICATION_CREDENTIALS":
            credential_path = Path(value)
            if not credential_path.is_absolute():
                value = str(env_file.parent / credential_path)
        os.environ[key] = value
