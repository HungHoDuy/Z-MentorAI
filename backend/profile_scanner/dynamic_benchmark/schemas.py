from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MarketJobEvidence(BaseModel):
    job_key: str
    job_title: str
    company: str = ""
    job_url: str = ""
    source: str = "unknown"
    source_updated_at: str = ""
    seniority: str = ""
    location_ids: list[str] = Field(default_factory=list)
    requirements_text: str = ""
    description_text: str = ""
    match_score: float = 0.0


class DynamicSkillCriterion(BaseModel):
    skill_id: str
    label: str
    aliases: list[str]
    job_count: int
    job_share: float
    weight: float
    tier: str


class DynamicBenchmarkSnapshot(BaseModel):
    benchmark_id: str
    cache_key: str
    compiler_version: str
    role_query: str
    normalized_role: str
    level: str
    location_id: str
    market: str = "vietnam"
    status: str
    confidence: str
    confidence_score: float
    window_days: int
    window_start: str
    window_end: str
    cohort_size: int
    distinct_company_count: int
    source_collections: list[str]
    source_names: list[str]
    skill_criteria: list[DynamicSkillCriterion]
    education_keywords: list[str] = Field(default_factory=list)
    evidence_sources: list[dict[str, Any]] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    vocabulary_source: str = "deterministic"
    embedding_model: str
    generated_at: datetime
    expires_at: datetime

    def as_firestore_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="python")

    def as_scoring_benchmark(self) -> dict[str, Any]:
        essential = [item.skill_id for item in self.skill_criteria if item.tier == "essential"]
        supporting = [item.skill_id for item in self.skill_criteria if item.tier != "essential"]
        aliases = {item.skill_id: item.aliases for item in self.skill_criteria}
        weights = {item.skill_id: item.weight for item in self.skill_criteria}
        return {
            "label": self.normalized_role,
            "aliases": [self.role_query, self.normalized_role],
            "core_skills": essential,
            "essential_skill_groups": [[skill] for skill in essential],
            "supporting_skills": supporting,
            "education_keywords": self.education_keywords,
            "skill_aliases": aliases,
            "skill_weights": weights,
            "scoring_policy": "essential_plus_best_supporting_v1",
            "supporting_target_count": min(4, len(supporting)),
            "level": self.level,
            "scorable": self.status == "ready",
        }
