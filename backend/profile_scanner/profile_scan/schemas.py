from typing import Optional

from pydantic import BaseModel


class ProfileRequest(BaseModel):
    user_id: str
    background_info: str = ""
    cv_document_id: Optional[str] = None


class ProfileResponse(BaseModel):
    status: str
    feature: str = "profile_scan"
    scan_status: str
    cv_document_id: Optional[str] = None
    message_vi: str
    next_status: str = "pending_extraction"
