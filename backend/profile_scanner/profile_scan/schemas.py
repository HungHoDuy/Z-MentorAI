from pydantic import BaseModel


class ProfileRequest(BaseModel):
    user_id: str
    background_info: str


class ProfileResponse(BaseModel):
    status: str
    feature: str = "profile_scan"
    analysis: str
