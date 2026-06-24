from typing import Any

from pydantic import BaseModel, Field


class StructuredExperience(BaseModel):
    title: str = ""
    organization: str = ""
    duration: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    impact_evidence: list[str] = Field(default_factory=list)


class StructuredEducation(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    duration: str = ""
    evidence: str = ""


class StructuredProject(BaseModel):
    name: str = ""
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    impact_evidence: list[str] = Field(default_factory=list)
    url: str = ""


class StructuredProfile(BaseModel):
    extraction_source: str = "ai"
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
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    def as_firestore_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
