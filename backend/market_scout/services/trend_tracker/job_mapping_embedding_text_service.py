from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from backend.market_scout.repositories.trend_tracker.trend_job_fact_repository import job_category_trend_fact_from_document
from backend.market_scout.schemas.trend_tracker.job_category_trend import JobCategoryTrendJobFact


DEFAULT_REQUIREMENTS_MAX_CHARS = 900
DEFAULT_DESCRIPTION_MAX_CHARS = 700


class JobMappingEmbeddingTextService:
    """Build stable embedding text for role/category/family mapping from trend job facts."""

    def __init__(
        self,
        *,
        requirements_max_chars: int = DEFAULT_REQUIREMENTS_MAX_CHARS,
        description_max_chars: int = DEFAULT_DESCRIPTION_MAX_CHARS,
    ) -> None:
        if requirements_max_chars <= 0 or description_max_chars <= 0:
            raise ValueError("Text limits must be positive.")
        self.requirements_max_chars = requirements_max_chars
        self.description_max_chars = description_max_chars

    def build_text(self, document_id: str, source_data: Mapping[str, Any]) -> str:
        fact = job_category_trend_fact_from_document(document_id, source_data)
        if fact is None:
            return ""
        return self.build_text_from_fact(fact)

    def build_text_from_fact(self, fact: JobCategoryTrendJobFact) -> str:
        lines = [
            _line("Job title", fact.job_title),
            _line("Job categories", ", ".join(fact.job_category_ids)),
            _line("Job families", ", ".join(fact.job_family_ids)),
            _line("Raw category labels", ", ".join(fact.raw_job_category_labels)),
            _line("Seniority", fact.seniority),
            _line("Employment type", fact.employment_type),
            _line("Requirements", _truncate(fact.requirements_text, self.requirements_max_chars)),
            _line("Description", _truncate(fact.description_text, self.description_max_chars)),
        ]
        return "\n".join(line for line in lines if line)


def build_job_mapping_document(
    *,
    document_id: str,
    source_collection: str,
    fact: JobCategoryTrendJobFact,
    embedding_text: str,
    embedding_model: str,
    embedding_updated_at: str,
) -> dict[str, Any]:
    return {
        "job_key": fact.job_key,
        "source_document_id": document_id,
        "job_url": fact.job_url,
        "job_title": fact.job_title,
        "company": fact.company,
        "location_ids": list(fact.location_ids),
        "source_expires_at": fact.source_expires_at.isoformat() if fact.source_expires_at else None,
        "raw_job_category_labels": list(fact.raw_job_category_labels),
        "job_category_ids": list(fact.job_category_ids),
        "job_family_ids": list(fact.job_family_ids),
        "embedding_text": embedding_text,
        "embedding_model": embedding_model,
        "embedding_updated_at": embedding_updated_at,
    }


def _line(label: str, value: str | None) -> str:
    if not value:
        return ""
    text = " ".join(str(value).split())
    if not text:
        return ""
    return f"{label}: {text}"


def _truncate(value: str | None, max_chars: int) -> str | None:
    if not value:
        return None
    text = " ".join(str(value).split())
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0]