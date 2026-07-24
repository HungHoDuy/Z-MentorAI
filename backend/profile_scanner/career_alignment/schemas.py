from pydantic import BaseModel, Field


class CareerAlignmentResponse(BaseModel):
    status: str
    feature: str = "career_alignment"
    user_id: str
    target_role: str | None = None
    benchmark_profile_id: str | None = None
    benchmark_type: str | None = None
    benchmark_version: str | None = None
    cv_readiness_score: float | None = None
    holland_alignment_score: float | None = None
    career_alignment_score: float | None = None
    alignment_state: str = "insufficient_data"
    conflict_severity: str = "unknown"
    missing_components: list[str] = Field(default_factory=list)
    holland_top_code: str | None = None
    mi_top_dimensions: list[str] = Field(default_factory=list)
    evidence_summary_vi: list[str] = Field(default_factory=list)
    recommendations_vi: list[str] = Field(default_factory=list)
    rule_version: str = "career-alignment-v1"
    generated_at: str
