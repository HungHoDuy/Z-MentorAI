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
    source: str = "chat"


class HollandScoreResponse(BaseModel):
    status: str
    feature: str = "holland_assessment"
    assessment_id: str
    user_id: str
    scores: dict[str, float]
    raw_scores: dict[str, int]
    top_code: str
    interpretation_vi: str
    answered_count: int
    missing_question_ids: list[str]
    created_at: str
