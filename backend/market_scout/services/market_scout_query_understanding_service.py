from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from backend.market_scout.schemas import MarketScoutIntent
from backend.market_scout.schemas.market_scout_query_understanding import (
    MarketScoutQueryUnderstanding,
    TrendQueryUnderstanding,
)
from backend.market_scout.schemas.trend_tracker.trend_query import TrendQueryIntent
from backend.market_scout.services.salary_benchmark.salary_query_normalizer import SalaryQueryNormalizer


DEFAULT_LLM_MODEL = "gemini-2.5-flash"
DEFAULT_VERTEX_LOCATION = "us-central1"
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
SYSTEM_PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "market_scout_query_understanding_system_prompt.txt"


class ChatModel(Protocol):
    def invoke(self, input: Any, **kwargs: Any) -> Any:
        ...


class MarketScoutQueryUnderstandingService:
    """Classify Market Scout queries and extract route-specific structured inputs."""

    def __init__(
        self,
        *,
        llm: ChatModel | None = None,
        salary_query_normalizer: SalaryQueryNormalizer | None = None,
        model_name: str | None = None,
        project: str | None = None,
        location: str | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 512,
        use_llm_for_intent: bool = False,
    ) -> None:
        _load_env_file()
        self._llm = llm
        self.salary_query_normalizer = salary_query_normalizer or SalaryQueryNormalizer()
        self.model_name = model_name or os.getenv("MARKET_SCOUT_QUERY_UNDERSTANDING_MODEL", DEFAULT_LLM_MODEL)
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.getenv("MARKET_SCOUT_VERTEX_LOCATION", DEFAULT_VERTEX_LOCATION)
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.use_llm_for_intent = use_llm_for_intent

    def understand(self, user_query: str) -> MarketScoutQueryUnderstanding:
        heuristic_intent = _classify_intent(user_query)

        if heuristic_intent is MarketScoutIntent.SALARY_BENCHMARK:
            return MarketScoutQueryUnderstanding(
                intent=heuristic_intent,
                salary_query=self.salary_query_normalizer.extract(user_query),
                confidence="medium",
                source="salary_query_normalizer",
            )

        if heuristic_intent is MarketScoutIntent.TREND_TRACKER:
            trend_query = self._understand_trend(user_query)
            return MarketScoutQueryUnderstanding(
                intent=heuristic_intent,
                trend_query=trend_query,
                confidence=trend_query.confidence,
                source="llm" if self._llm is not None else "trend_fallback",
            )

        if self.use_llm_for_intent:
            parsed = self._invoke_llm(user_query)
            llm_intent = MarketScoutIntent.from_value(_optional_text(parsed.get("intent")))
            if llm_intent is MarketScoutIntent.SALARY_BENCHMARK:
                return MarketScoutQueryUnderstanding(
                    intent=llm_intent,
                    salary_query=self.salary_query_normalizer.extract(user_query),
                    confidence=_confidence(parsed.get("confidence")),
                    source="llm",
                )
            if llm_intent is MarketScoutIntent.TREND_TRACKER:
                trend_query = _trend_understanding_from_payload(parsed)
                return MarketScoutQueryUnderstanding(
                    intent=llm_intent,
                    trend_query=trend_query,
                    confidence=trend_query.confidence,
                    source="llm",
                )

        return MarketScoutQueryUnderstanding(intent=MarketScoutIntent.UNCLEAR, confidence="low")

    def _understand_trend(self, user_query: str) -> TrendQueryUnderstanding:
        try:
            return _trend_understanding_from_payload(self._invoke_llm(user_query))
        except Exception:
            return TrendQueryUnderstanding(
                intent=_fallback_trend_intent(user_query),
                confidence="low",
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


def _trend_understanding_from_payload(payload: dict[str, Any]) -> TrendQueryUnderstanding:
    return TrendQueryUnderstanding(
        intent=_trend_intent(payload.get("trend_intent")),
        role_mention=_optional_text(payload.get("role_mention")),
        location_text=_optional_text(payload.get("location_text")),
        job_category_hint=_optional_text(payload.get("job_category_hint")),
        job_family_hint=_optional_text(payload.get("job_family_hint")),
        requested_signal=_optional_text(payload.get("requested_signal")),
        confidence=_confidence(payload.get("confidence")),
    )


def _classify_intent(query: str) -> MarketScoutIntent:
    normalized = _text_key(query)
    if any(keyword in normalized for keyword in _SALARY_KEYWORDS):
        return MarketScoutIntent.SALARY_BENCHMARK
    if any(keyword in normalized for keyword in _TREND_KEYWORDS):
        return MarketScoutIntent.TREND_TRACKER
    return MarketScoutIntent.UNCLEAR


def _fallback_trend_intent(query: str) -> TrendQueryIntent:
    normalized = _text_key(query)
    if any(keyword in normalized for keyword in ("automation", "tu dong hoa", "ai thay the", "thay the", "bi thay the", "mat viec", "ai")):
        return TrendQueryIntent.AUTOMATION_EXPOSURE
    if any(keyword in normalized for keyword in ("skill", "ky nang", "yeu cau")):
        return TrendQueryIntent.CURRENT_SKILL_DEMAND
    if any(keyword in normalized for keyword in ("outlook", "forecast", "du bao", "tuong lai")):
        return TrendQueryIntent.EXTERNAL_OUTLOOK
    return TrendQueryIntent.CURRENT_DEMAND


def _trend_intent(value: Any) -> TrendQueryIntent:
    text = _optional_text(value)
    if not text:
        return TrendQueryIntent.CURRENT_DEMAND
    try:
        return TrendQueryIntent(text)
    except ValueError:
        return _fallback_trend_intent(text)


def _confidence(value: Any) -> str:
    text = _optional_text(value)
    if text in {"high", "medium", "low"}:
        return text
    return "low"


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object from query understanding LLM.")
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


def _text_key(value: str | None) -> str:
    if not value:
        return ""
    text = str(value).replace(chr(273), "d").replace(chr(272), "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = text.casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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


_SALARY_KEYWORDS = (
    "salary",
    "compensation",
    "pay",
    "wage",
    "benchmark",
    "luong",
    "muc luong",
    "thu nhap",
)

_TREND_KEYWORDS = (
    "trend",
    "demand",
    "forecast",
    "decline",
    "automation",
    "xu huong",
    "nhu cau",
    "tuyen nhieu",
    "tuyen dung",
    "dang tuyen",
    "viec lam",
    "hot",
    "ai",
    "thay the",
    "bi thay the",
    "tu dong hoa",
    "mat viec",
)

