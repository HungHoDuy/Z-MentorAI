from fastapi import APIRouter

from career_alignment.schemas import CareerAlignmentResponse
from career_alignment.service import synthesize_career_alignment


router = APIRouter(prefix="/alignment", tags=["career-alignment"])


@router.post("/synthesize/{user_id}", response_model=CareerAlignmentResponse)
async def synthesize(user_id: str):
    return await synthesize_career_alignment(user_id)
