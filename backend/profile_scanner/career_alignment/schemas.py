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
    executive_summary_vi: str = ""
    strengths_vi: list[str] = Field(default_factory=list)
    watchouts_vi: list[str] = Field(default_factory=list)
    action_plan_vi: list[str] = Field(default_factory=list)
    learning_strategy_vi: str = ""
    guidance_source: str = "deterministic_fallback"
    guidance_version: str = "profile-guidance-v1"
    rule_version: str = "career-alignment-v2"
    generated_at: str
