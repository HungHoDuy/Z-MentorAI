from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from backend.market_scout.flows.trend_tracker_flow import TrendTrackerFlowResult
from backend.market_scout.schemas.trend_tracker.trend_summary import TrendSummaryResult
from backend.market_scout.services.trend_tracker.trend_summary_service import TrendSummaryService


DEFAULT_LLM_MODEL = "gemini-2.5-flash"
DEFAULT_VERTEX_LOCATION = "us-central1"
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
SYSTEM_PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "trend_summary_system_prompt.txt"


class ChatModel(Protocol):
    def invoke(self, input: Any, **kwargs: Any) -> Any:
        ...


class TrendLlmSummaryService:
    """Use an LLM only to phrase deterministic Trend Tracker evidence."""

    def __init__(
        self,
        *,
        llm: ChatModel | None = None,
        fallback_service: TrendSummaryService | None = None,
        model_name: str | None = None,
        project: str | None = None,
        location: str | None = None,
        temperature: float = 0.2,
        max_output_tokens: int = 1024,
    ) -> None:
        _load_env_file()
        self.model_name = model_name or os.getenv("MARKET_SCOUT_TREND_LLM_MODEL", DEFAULT_LLM_MODEL)
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.getenv("MARKET_SCOUT_VERTEX_LOCATION", DEFAULT_VERTEX_LOCATION)
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self._llm = llm
        self.fallback_service = fallback_service or TrendSummaryService()

    def summarize(self, result: TrendTrackerFlowResult) -> TrendSummaryResult:
        fallback = self.fallback_service.summarize(result)
        llm = self._llm or self._build_llm()
        try:
            response = llm.invoke(
                [
                    SystemMessage(content=_load_system_prompt()),
                    HumanMessage(content=json.dumps(self._payload(result, fallback), ensure_ascii=False)),
                ]
            )
            answer = _response_to_text(response).strip()
            if not _is_complete_answer(answer):
                raise ValueError("LLM returned an incomplete trend summary.")
        except Exception:
            return fallback

        return TrendSummaryResult(
            answer=answer,
            confidence=fallback.confidence,
            sources=fallback.sources,
            limitations=fallback.limitations,
            composer_version="trend-llm-summary-v1",
        )

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

    @staticmethod
    def _payload(result: TrendTrackerFlowResult, fallback: TrendSummaryResult) -> dict[str, Any]:
        return {
            "query": result.to_dict()["query"],
            "signal": result.signal.to_dict(),
            "deterministic_draft": fallback.answer,
            "instructions": {
                "language": "Vietnamese",
                "use_only_provided_data": True,
                "do_not_invent_metrics_or_sources": True,
                "do_not_claim_directional_trend_when_directional_trend_is_false": True,
                "preserve_limitations": True,
                "keep_answer_concise_and_user_friendly": True,
            },
        }


def _load_system_prompt(prompt_file: Path = SYSTEM_PROMPT_FILE) -> str:
    return prompt_file.read_text(encoding="utf-8")


def _is_complete_answer(answer: str) -> bool:
    if len(answer) < 40:
        return False
    return re.search(r"[.!?]\s*$", answer) is not None

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
