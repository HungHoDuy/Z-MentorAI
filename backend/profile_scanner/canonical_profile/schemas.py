from typing import Literal

from pydantic import BaseModel


class ProfileDecisionRequest(BaseModel):
    user_id: str
    cv_document_id: str
    decision: Literal["accept", "update", "overwrite", "reject"]


class ProfileDecisionResponse(BaseModel):
    status: str = "success"
    feature: str = "profile_confirmation"
    user_id: str
    cv_document_id: str
    decision: str
    profile_status: str
    profile_version: int | None = None
    active_cv_document_id: str | None = None
    message_vi: str
