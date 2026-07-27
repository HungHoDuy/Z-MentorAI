from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from backend.market_scout.services.salary_benchmark.salary_benchmark_service import SalaryBenchmarkResult


DEFAULT_LLM_MODEL = "gemini-2.5-flash"
DEFAULT_VERTEX_LOCATION = "us-central1"
PROMPT_VERSION = "salary-summary-v1"
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
SYSTEM_PROMPT_FILE = Path(__file__).resolve().parents[2] / "prompts" / "salary_summary_system_prompt.txt"


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
        payload = self._build_payload(user_query, benchmark)
        try:
            llm = self._llm or self._build_llm()
            response = llm.invoke(
                [
                    SystemMessage(content=_load_system_prompt()),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False, indent=2)),
                ]
            )
            answer = _response_to_text(response).strip()
            if answer:
                return SalarySummaryResult(
                    answer=_append_salary_source_links(answer, benchmark),
                    model_name=self.model_name,
                )
        except Exception:
            pass

        return SalarySummaryResult(
            answer=_append_salary_source_links(_deterministic_salary_answer(benchmark), benchmark),
            model_name=f"{self.model_name}:fallback",
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





def _append_salary_source_links(answer: str, benchmark: SalaryBenchmarkResult) -> str:
    sources = list(benchmark.sources or [])
    if not sources:
        return answer
    if any(source.job_url and source.job_url in answer for source in sources):
        return answer

    lines = _salary_source_link_lines(sources)
    if not lines:
        return answer
    return f"{answer.rstrip()}\n\nMot so JD lien quan ban co the tham khao:\n" + "\n".join(lines)


def _salary_source_link_lines(sources: list[Any]) -> list[str]:
    lines: list[str] = []
    seen_urls: set[str] = set()
    for source in sources[:5]:
        url = str(getattr(source, "job_url", "") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        label = _short_salary_source_label(getattr(source, "company", None), getattr(source, "job_title", None))
        salary_text = _source_salary_text(source)
        suffix = f": {salary_text}" if salary_text else ""
        lines.append(f"- [{label}]({url}){suffix}")
    return lines


def _short_salary_source_label(company: Any, job_title: Any) -> str:
    company_text = _compact_text(company, fallback="Cong ty")
    title_text = _compact_text(job_title, fallback="JD lien quan")
    label = f"{company_text} - {title_text}"
    words = label.split()
    if len(words) <= 14:
        return label
    return " ".join(words[:14]).rstrip(" -")


def _source_salary_text(source: Any) -> str | None:
    salary_min = getattr(source, "salary_min_vnd", None)
    salary_max = getattr(source, "salary_max_vnd", None)
    if salary_min is None and salary_max is None:
        return None
    return f"{_format_vnd_million(int(salary_min or 0))} - {_format_vnd_million(int(salary_max or 0))} trieu VND/thang"


def _compact_text(value: Any, *, fallback: str) -> str:
    text = " ".join(str(value or "").replace("_", " ").replace("-", " ").split())
    return text or fallback

def _load_system_prompt(prompt_file: Path = SYSTEM_PROMPT_FILE) -> str:
    return prompt_file.read_text(encoding="utf-8")

def _salary_range_text(benchmark: SalaryBenchmarkResult) -> str | None:
    if benchmark.salary_range is None:
        return None
    salary_range = benchmark.salary_range
    return f"{_format_vnd_million(salary_range.min)} - {_format_vnd_million(salary_range.max)} trieu VND/thang"


def _deterministic_salary_answer(benchmark: SalaryBenchmarkResult) -> str:
    if benchmark.salary_range is None:
        return (
            "Chua du du lieu de tinh benchmark luong dang tin cay cho vi tri nay. "
            "Ket qua hien tai khong co mau luong phu hop sau khi loc du lieu."
        )

    role = benchmark.job_title or "vi tri nay"
    location = benchmark.location or "khu vuc dang hoi"
    experience = (
        f" voi {benchmark.experience_years} nam kinh nghiem"
        if benchmark.experience_years is not None
        else ""
    )
    return (
        f"Muc luong tham khao cho {role} tai {location}{experience} la khoang "
        f"{_salary_range_text(benchmark)}, dua tren {benchmark.sample_size} mau viec lam phu hop. "
        f"Do tin cay: {benchmark.confidence}."
    )

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
