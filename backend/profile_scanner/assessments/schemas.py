from typing import Optional

from pydantic import BaseModel, Field


class AssessmentQuestion(BaseModel):
    id: str
    dimension: str
    text_vi: str


class AssessmentStartResponse(BaseModel):
    status: str
    feature: str = "assessment"
    assessment_type: str
    assessment_version: str
    title: str
    eyebrow_vi: str
    description_vi: str
    result_label_vi: str
    scale: dict[str, str]
    dimension_labels: dict[str, str]
    questions: list[AssessmentQuestion]
    latest_result: Optional[dict] = None


class AssessmentAnswer(BaseModel):
    question_id: str
    score: int = Field(ge=1, le=5)


class AssessmentScoreRequest(BaseModel):
    user_id: str
    answers: list[AssessmentAnswer]
    session_id: Optional[str] = None
    source: str = "chat"


class AssessmentScoreResponse(BaseModel):
    status: str
    feature: str = "assessment"
    assessment_id: str
    assessment_type: str
    assessment_version: str
    user_id: str
    session_id: Optional[str] = None
    scores: dict[str, float]
    raw_scores: dict[str, int]
    top_dimensions: list[str]
    result_code: str
    result_label_vi: str
    interpretation_vi: str
    recommendations_vi: list[str]
    answered_count: int
    missing_question_ids: list[str]
    created_at: str
