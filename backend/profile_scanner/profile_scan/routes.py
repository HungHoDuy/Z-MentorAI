from fastapi import APIRouter

from profile_scan.schemas import ProfileRequest, ProfileResponse
from profile_scan.service import analyze_profile


router = APIRouter(tags=["profile"])


@router.post("/scan", response_model=ProfileResponse)
async def scan_profile(request: ProfileRequest):
    return await analyze_profile(request)
