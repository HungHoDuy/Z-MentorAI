import uuid

from fastapi import APIRouter, HTTPException

from assessments.definitions import ASSESSMENT_DEFINITIONS
from assessments.repository import get_latest_assessment_result, save_assessment_result
from assessments.scoring import build_question_set_hash
from assessments.schemas import AssessmentScoreRequest, AssessmentScoreResponse, AssessmentStartResponse
from assessments.service import get_assessment_definition, score_assessment_answers
from canonical_profile.repository import get_canonical_profile
from core.config import logger, settings
from guidance.service import generate_mi_guidance


router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.get("")
async def list_assessments():
    unique_definitions = {
        definition.assessment_type: definition
        for definition in ASSESSMENT_DEFINITIONS.values()
    }
    return {
        "status": "success",
        "feature": "assessment_catalog",
        "assessments": [
            {
                "assessment_type": definition.assessment_type,
                "assessment_version": definition.version,
                "title": definition.title,
                "eyebrow_vi": definition.eyebrow_vi,
                "description_vi": definition.description_vi,
                "question_count": len(definition.questions),
                "dimension_labels": definition.dimension_labels,
            }
            for definition in unique_definitions.values()
        ],
    }


@router.get("/{assessment_type}/start/{user_id}", response_model=AssessmentStartResponse)
async def start_assessment(assessment_type: str, user_id: str):
    definition = get_assessment_definition(assessment_type)
    try:
        latest_result = await get_latest_assessment_result(user_id, definition.assessment_type)
    except Exception as exc:
        logger.exception(
            "Failed to load latest assessment result; continuing without history",
            extra={
                "user_id": user_id,
                "assessment_type": definition.assessment_type,
                "collection": settings.assessments_collection_name,
                "error_type": type(exc).__name__,
            },
        )
        latest_result = None

    return AssessmentStartResponse(
        status="success",
        assessment_type=definition.assessment_type,
        assessment_version=definition.version,
        question_set_hash=build_question_set_hash(definition.questions),
        attempt_id=str(uuid.uuid4()),
        title=definition.title,
        eyebrow_vi=definition.eyebrow_vi,
        description_vi=definition.description_vi,
        result_label_vi=definition.result_label_vi,
        scale=definition.scale,
        dimension_labels=definition.dimension_labels,
        questions=definition.questions,
        latest_result=latest_result,
    )


@router.post("/{assessment_type}/score", response_model=AssessmentScoreResponse)
async def score_assessment(assessment_type: str, request: AssessmentScoreRequest):
    result = score_assessment_answers(assessment_type, request)
    result_payload = result.model_dump() if hasattr(result, "model_dump") else result.dict()
    definition = get_assessment_definition(assessment_type)
    if definition.assessment_type == "multiple_intelligences":
        try:
            profile = await get_canonical_profile(request.user_id)
        except Exception as exc:
            logger.warning(
                "Could not load canonical profile for MI guidance",
                extra={"user_id": request.user_id, "error_type": type(exc).__name__},
            )
            profile = None
        guidance, guidance_source = await generate_mi_guidance(
            result=result_payload,
            dimension_labels=definition.dimension_labels,
            fallback_recommendations=result_payload.get("recommendations_vi", []),
            profile=profile,
        )
        result_payload.update({
            "interpretation_vi": guidance.learning_profile_summary_vi,
            "recommendations_vi": guidance.learning_strategies_vi,
            "learning_profile_summary_vi": guidance.learning_profile_summary_vi,
            "learning_strategies_vi": guidance.learning_strategies_vi,
            "application_examples_vi": guidance.application_examples_vi,
            "guidance_source": guidance_source,
        })
    saved_result = await save_assessment_result(result_payload)
    return AssessmentScoreResponse(**saved_result)


@router.get("/{assessment_type}/latest/{user_id}")
async def get_latest_assessment(assessment_type: str, user_id: str):
    definition = get_assessment_definition(assessment_type)
    try:
        result = await get_latest_assessment_result(user_id, definition.assessment_type)
    except Exception as exc:
        logger.exception(
            "Failed to load latest assessment result",
            extra={
                "user_id": user_id,
                "assessment_type": definition.assessment_type,
                "collection": settings.assessments_collection_name,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail="Assessment history is temporarily unavailable.",
        ) from exc

    if not result:
        raise HTTPException(status_code=404, detail="No assessment result found for this user.")
    return result
