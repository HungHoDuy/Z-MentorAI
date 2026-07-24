from typing import Any

from pydantic import BaseModel, Field


FIRESTORE_BENCHMARK_SNAPSHOT_FIELDS = (
    "benchmark_id",
    "benchmark_type",
    "normalized_role",
    "level",
    "location_id",
    "market",
    "status",
    "confidence",
    "confidence_score",
    "window_days",
    "window_start",
    "window_end",
    "cohort_size",
    "distinct_company_count",
    "compiler_version",
    "generated_at",
    "expires_at",
    "riasec",
    "riasec_source",
)


class ScoreDimension(BaseModel):
    key: str
    label: str
    score: float
    weight: float
    evidence: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class ProfileAnalysisResult(BaseModel):
    status: str = "success"
    feature: str = "profile_scan"
    scan_status: str = "profile_analysis_completed"
    cv_document_id: str
    target_role: str | None = None
    target_role_source: str = "unresolved"
    target_role_confidence: float = 0.0
    benchmark_status: str = "resolved"
    benchmark_profile_id: str | None = None
    benchmark_version: str
    scoring_version: str
    benchmark_type: str = "static"
    benchmark_confidence: str | None = None
    benchmark_confidence_score: float | None = None
    benchmark_sample_size: int | None = None
    benchmark_distinct_companies: int | None = None
    benchmark_sources: list[dict[str, Any]] = Field(default_factory=list)
    benchmark_snapshot: dict[str, Any] | None = None
    grade: str | None = None
    total_score: float | None = None
    score_dimensions: list[ScoreDimension]
    extracted_skills: list[str] = Field(default_factory=list)
    normalized_skills: list[dict[str, Any]] = Field(default_factory=list)
    raw_extracted_skills: list[str] = Field(default_factory=list)
    skill_normalization_version: str = "skill-normalization-v1"
    work_experiences: list[str] = Field(default_factory=list)
    education_records: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    missing_signals: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    benchmark_notes: list[str] = Field(default_factory=list)
    ai_extraction_used: bool = False
    ai_extraction_confidence: float | None = None
    structured_profile: dict[str, Any] | None = None
    candidate_identity: dict[str, str] = Field(default_factory=dict)
    analysis_artifact_gcs_uri: str | None = None
    analyzed_at: str
    message_vi: str

    def as_artifact_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def as_firestore_payload(self) -> dict[str, Any]:
        payload = self.as_artifact_payload()
        snapshot = payload.get("benchmark_snapshot")
        if isinstance(snapshot, dict):
            payload["benchmark_snapshot"] = {
                field: snapshot[field]
                for field in FIRESTORE_BENCHMARK_SNAPSHOT_FIELDS
                if snapshot.get(field) is not None
            }
        return payload
