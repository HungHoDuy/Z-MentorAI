from fastapi import APIRouter

from canonical_profile.schemas import (
    ProfileDecisionRequest,
    ProfileDecisionResponse,
)
from canonical_profile.service import confirm_profile_decision


router = APIRouter(prefix="/profiles", tags=["canonical-profile"])


@router.post("/confirm", response_model=ProfileDecisionResponse)
async def confirm_profile(request: ProfileDecisionRequest):
    return await confirm_profile_decision(request)
