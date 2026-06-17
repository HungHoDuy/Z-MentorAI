from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from backend.market_scout.services.salary_benchmark_service import SalaryBenchmarkResult


DEFAULT_LLM_MODEL = "gemini-2.5-flash"
DEFAULT_VERTEX_LOCATION = "us-central1"
PROMPT_VERSION = "salary-summary-v1"
ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class ChatModel(Protocol):
    def invoke(self, input: Any, **kwargs: Any) -> Any:
        ...


@dataclass(frozen=True)
class SalarySummaryResult:
    answer: str
    model_name: str
    prompt_version: str = PROMPT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "model_name": self.model_name,
            "prompt_version": self.prompt_version,
        }


class SalarySummaryService:
    """Use an LLM to summarize a deterministic salary benchmark result."""

    def __init__(
        self,
        *,
        llm: ChatModel | None = None,
        model_name: str | None = None,
        project: str | None = None,
        location: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
    ) -> None:
        _load_env_file()
        self.model_name = model_name or os.getenv("MARKET_SCOUT_LLM_MODEL", DEFAULT_LLM_MODEL)
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.getenv("MARKET_SCOUT_VERTEX_LOCATION", DEFAULT_VERTEX_LOCATION)
        self.temperature = temperature if temperature is not None else _env_float("MARKET_SCOUT_LLM_TEMPERATURE", 0.2)
        self.max_output_tokens = (
            max_output_tokens
            if max_output_tokens is not None
            else _env_int("MARKET_SCOUT_LLM_MAX_OUTPUT_TOKENS", 512)
        )
        self._llm = llm

    def summarize(self, user_query: str, benchmark: SalaryBenchmarkResult) -> SalarySummaryResult:
        llm = self._llm or self._build_llm()
        payload = self._build_payload(user_query, benchmark)
        try:
            response = llm.invoke(
                [
                    SystemMessage(content=_SYSTEM_PROMPT),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False, indent=2)),
                ]
            )
        except Exception as exc:
            raise RuntimeError(
                "Failed to summarize salary benchmark with Vertex AI model "
                f"'{self.model_name}' in location '{self.location}'. "
                "Check MARKET_SCOUT_LLM_MODEL / --llm-model and confirm the project has access to that model."
            ) from exc

        return SalarySummaryResult(
            answer=_response_to_text(response).strip(),
            model_name=self.model_name,
        )

    def _build_llm(self) -> ChatModel:
        try:
            from langchain_google_vertexai import ChatVertexAI
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency langchain-google-vertexai. Install backend/market_scout/requirements.txt first."
            ) from exc

        return ChatVertexAI(
            model=self.model_name,
            project=self.project,
            location=self.location,
            temperature=self.temperature,
            max_tokens=self.max_output_tokens,
            max_retries=1,
        )

    @staticmethod
    def _build_payload(user_query: str, benchmark: SalaryBenchmarkResult) -> dict[str, Any]:
        benchmark_dict = benchmark.to_dict()
        benchmark_dict["salary_range_text"] = _salary_range_text(benchmark)
        return {
            "user_query": user_query,
            "benchmark": benchmark_dict,
            "instructions": {
                "language": "Vietnamese",
                "use_only_provided_data": True,
                "do_not_recalculate_salary": True,
                "do_not_invent_sources": True,
                "keep_answer_concise": True,
            },
        }


_SYSTEM_PROMPT = """You are the Salary Benchmark summary writer for Market Scout.

Rules:
- Write the final answer in Vietnamese.
- Use only the JSON data provided by the user message.
- Do not invent salaries, companies, URLs, confidence values, or extra market facts.
- Do not recalculate salary; use salary_range_text or salary_range exactly as provided.
- If salary_range is null, say the available data is not sufficient for a reliable benchmark.
- If confidence is low, clearly mention that the result should be treated as a weak estimate.
- Keep the answer concise and suitable for an end user.
- Include the most relevant source URLs only when they are present in the provided JSON.
"""


def _salary_range_text(benchmark: SalaryBenchmarkResult) -> str | None:
    if benchmark.salary_range is None:
        return None
    salary_range = benchmark.salary_range
    return f"{_format_vnd_million(salary_range.min)} - {_format_vnd_million(salary_range.max)} trieu VND/thang"


def _format_vnd_million(value: int) -> str:
    million_value = value / 1_000_000
    if million_value.is_integer():
        return f"{int(million_value)}"
    return f"{million_value:.1f}"


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


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


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
                credential_path = env_file.parent / credential_path
            value = str(credential_path)

        os.environ[key] = value
