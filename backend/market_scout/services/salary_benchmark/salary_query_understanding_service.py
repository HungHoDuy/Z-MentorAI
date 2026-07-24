from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from backend.market_scout.schemas.salary_benchmark.salary import SalarySearchQuery
from backend.market_scout.services.salary_benchmark.salary_query_normalizer import SalaryQueryNormalizer


DEFAULT_LLM_MODEL = "gemini-2.5-flash"
DEFAULT_VERTEX_LOCATION = "us-central1"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
SYSTEM_PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts" / "salary_query_understanding_system_prompt.txt"


class ChatModel(Protocol):
    def invoke(self, input: Any, **kwargs: Any) -> Any:
        ...


class SalaryQueryUnderstandingService:
    """LLM-first salary query extraction with deterministic normalizer fallback."""

    def __init__(
        self,
        *,
        llm: ChatModel | None = None,
        normalizer: SalaryQueryNormalizer | None = None,
        model_name: str | None = None,
        project: str | None = None,
        location: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 256,
    ) -> None:
        _load_env_file()
        self._llm = llm
        self.normalizer = normalizer or SalaryQueryNormalizer()
        self.model_name = model_name or os.getenv("MARKET_SCOUT_QUERY_UNDERSTANDING_MODEL", DEFAULT_LLM_MODEL)
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.getenv("MARKET_SCOUT_VERTEX_LOCATION", DEFAULT_VERTEX_LOCATION)
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def extract(self, user_query: str) -> SalarySearchQuery:
        fallback = self.normalizer.extract(user_query)
        try:
            payload = self._invoke_llm(user_query)
        except Exception:
            return fallback

        job_title = _optional_text(payload.get("job_title"))
        location = _optional_text(payload.get("location")) or fallback.location
        experience_years = _to_int_or_none(payload.get("experience_years"))
        if experience_years is None:
            experience_years = fallback.experience_years
        currency = _currency(payload.get("currency")) or fallback.currency

        if not job_title:
            return SalarySearchQuery(
                raw_query=user_query,
                job_title=None,
                job_title_normalized=None,
                location=location,
                location_normalized=self.normalizer.normalize_location(location) if location else None,
                experience_years=experience_years,
                currency=currency,
            )

        normalized_title = self.normalizer.normalize_job_title(job_title)
        if not normalized_title:
            return fallback

        return SalarySearchQuery(
            raw_query=user_query,
            job_title=job_title,
            job_title_normalized=normalized_title,
            location=location,
            location_normalized=self.normalizer.normalize_location(location) if location else None,
            experience_years=experience_years,
            currency=currency,
        )

    def _invoke_llm(self, user_query: str) -> dict[str, Any]:
        llm = self._llm or self._build_llm()
        response = llm.invoke(
            [
                SystemMessage(content=_load_system_prompt()),
                HumanMessage(content=json.dumps({"user_query": user_query}, ensure_ascii=False)),
            ]
        )
        return _parse_json_object(_response_to_text(response))

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


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _to_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _currency(value: Any) -> str | None:
    text = _optional_text(value)
    if not text:
        return None
    text = text.upper()
    if text in {"VND", "USD"}:
        return text
    return None


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object from salary query understanding LLM.")
    return data


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
