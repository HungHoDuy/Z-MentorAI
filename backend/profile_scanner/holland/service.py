import datetime
import uuid
from collections import defaultdict

from fastapi import HTTPException

from holland.questions import (
    DIMENSION_LABELS,
    HOLLAND_QUESTIONS,
    INTERPRETATION_BY_TOP,
    QUESTION_BY_ID,
)
from holland.schemas import HollandScoreRequest, HollandScoreResponse


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def score_holland_answers(request: HollandScoreRequest) -> HollandScoreResponse:
    answered_by_id = {answer.question_id: answer for answer in request.answers}
    unknown_ids = sorted(set(answered_by_id) - set(QUESTION_BY_ID))
    if unknown_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown Holland question ids: {', '.join(unknown_ids)}",
        )

    raw_scores = {dimension: 0 for dimension in DIMENSION_LABELS}
    counts = defaultdict(int)
    for answer in request.answers:
        question = QUESTION_BY_ID[answer.question_id]
        raw_scores[question.dimension] += answer.score
        counts[question.dimension] += 1

    scores = {}
    for dimension in DIMENSION_LABELS:
        max_score = max(counts[dimension] * 5, 1)
        scores[dimension] = round(raw_scores[dimension] / max_score, 2)

    sorted_dimensions = sorted(
        DIMENSION_LABELS.keys(),
        key=lambda dimension: (scores[dimension], raw_scores[dimension]),
        reverse=True,
    )
    top_code = "-".join(sorted_dimensions[:3])
    top_dimension = sorted_dimensions[0]
    missing_question_ids = [
        question.id for question in HOLLAND_QUESTIONS
        if question.id not in answered_by_id
    ]

    return HollandScoreResponse(
        status="success",
        assessment_id=str(uuid.uuid4()),
        user_id=request.user_id,
        scores=scores,
        raw_scores=raw_scores,
        top_code=top_code,
        interpretation_vi=INTERPRETATION_BY_TOP[top_dimension],
        answered_count=len(request.answers),
        missing_question_ids=missing_question_ids,
        created_at=utc_now(),
    )
