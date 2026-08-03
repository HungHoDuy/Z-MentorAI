from typing import Literal, Optional

from pydantic import BaseModel, Field


RIASECDimension = Literal["R", "I", "A", "S", "E", "C"]


class HollandQuestion(BaseModel):
    id: str
    dimension: RIASECDimension
    text_vi: str


class HollandQuestionsResponse(BaseModel):
    status: str
    feature: str = "holland_assessment"
    assessment_version: str
    question_set_hash: str
    attempt_id: str
    scale: dict
    questions: list[HollandQuestion]


class HollandStartResponse(HollandQuestionsResponse):
    latest_result: Optional[dict] = None


class HollandAnswer(BaseModel):
    question_id: str
    score: int = Field(ge=1, le=5)


class HollandScoreRequest(BaseModel):
    user_id: str
    answers: list[HollandAnswer]
    session_id: Optional[str] = None
    attempt_id: Optional[str] = None
    question_set_hash: Optional[str] = None
    source: str = "chat"


class HollandScoreResponse(BaseModel):
    status: str
    feature: str = "holland_assessment"
    assessment_id: str
    assessment_version: str
    question_set_hash: str
    user_id: str
    session_id: Optional[str] = None
    attempt_id: Optional[str] = None
    scores: dict[str, float]
    raw_scores: dict[str, int]
    top_code: str
    tied_top_dimensions: list[str] = Field(default_factory=list)
    score_margin: float | None = None
    tie_break_policy: str = "definition_order"
    interpretation_vi: str
    answered_count: int
    missing_question_ids: list[str]
    created_at: str
