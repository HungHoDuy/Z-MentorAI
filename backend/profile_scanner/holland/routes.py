from fastapi import APIRouter, HTTPException

from core.config import logger, settings
from holland.questions import HOLLAND_QUESTIONS, HOLLAND_SCALE
from holland.repository import get_latest_holland_assessment, save_holland_assessment
from holland.schemas import (
    HollandQuestionsResponse,
    HollandScoreRequest,
    HollandScoreResponse,
    HollandStartResponse,
)
from holland.service import score_holland_answers


router = APIRouter(prefix="/holland", tags=["holland"])


@router.get("/questions", response_model=HollandQuestionsResponse)
async def get_holland_questions():
    return HollandQuestionsResponse(
        status="success",
        scale=HOLLAND_SCALE,
        questions=HOLLAND_QUESTIONS,
    )


@router.get("/start/{user_id}", response_model=HollandStartResponse)
async def start_holland_assessment(user_id: str):
    try:
        latest_result = await get_latest_holland_assessment(user_id)
    except Exception as exc:
        # Starting the test should not fail only because optional history lookup is unavailable.
        logger.exception(
            "Failed to load latest Holland assessment; continuing without history",
            extra={
                "user_id": user_id,
                "collection": settings.holland_collection_name,
                "error_type": type(exc).__name__,
            },
        )
        latest_result = None

    return HollandStartResponse(
        status="success",
        latest_result=latest_result,
        scale=HOLLAND_SCALE,
        questions=HOLLAND_QUESTIONS,
    )


@router.post("/score", response_model=HollandScoreResponse)
async def score_holland_assessment(request: HollandScoreRequest):
    result = score_holland_answers(request)
    result_payload = result.model_dump() if hasattr(result, "model_dump") else result.dict()
    await save_holland_assessment(result_payload)
    return result


@router.get("/latest/{user_id}")
async def get_latest_holland_result(user_id: str):
    try:
        result = await get_latest_holland_assessment(user_id)
    except Exception as exc:
        logger.exception(
            "Failed to load latest Holland assessment",
            extra={
                "user_id": user_id,
                "collection": settings.holland_collection_name,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail="Holland assessment history is temporarily unavailable.",
        ) from exc

    if not result:
        raise HTTPException(status_code=404, detail="No Holland assessment found for this user.")
    return result
