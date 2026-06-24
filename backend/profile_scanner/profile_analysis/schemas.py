from typing import Any

from pydantic import BaseModel, Field


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
    target_role: str
    benchmark_profile_id: str
    benchmark_version: str
    grade: str
    total_score: float
    score_dimensions: list[ScoreDimension]
    extracted_skills: list[str] = Field(default_factory=list)
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
    analysis_artifact_gcs_uri: str | None = None
    analyzed_at: str
    message_vi: str

    def as_firestore_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
