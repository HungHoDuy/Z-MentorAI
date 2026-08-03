from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class NullSafeExtractionModel(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def use_defaults_for_null_values(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return {
            key: [item for item in item_value if item is not None]
            if isinstance(item_value, list)
            else item_value
            for key, item_value in value.items()
            if item_value is not None
        }


class StructuredExperience(NullSafeExtractionModel):
    title: str = ""
    organization: str = ""
    duration: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    impact_evidence: list[str] = Field(default_factory=list)


class StructuredEducation(NullSafeExtractionModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    duration: str = ""
    evidence: str = ""


class StructuredProject(NullSafeExtractionModel):
    name: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    impact_evidence: list[str] = Field(default_factory=list)
    url: str = ""


class ProfileIssue(NullSafeExtractionModel):
    field: str
    code: Literal["missing", "unclear", "needs_review"] = "needs_review"
    severity: Literal["info", "warning"] = "warning"


class StructuredProfile(NullSafeExtractionModel):
    extraction_source: str = "ai"
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin_url: str = ""
    github_url: str = ""
    portfolio_url: str = ""
    target_role_hint: str = ""
    headline: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    work_experiences: list[StructuredExperience] = Field(default_factory=list)
    education: list[StructuredEducation] = Field(default_factory=list)
    projects: list[StructuredProject] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    career_readiness_signals: list[str] = Field(default_factory=list)
    missing_or_unclear: list[str] = Field(default_factory=list)
    profile_issues: list[ProfileIssue] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    def as_firestore_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
