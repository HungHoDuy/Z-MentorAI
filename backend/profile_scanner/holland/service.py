import datetime
from collections import defaultdict

from fastapi import HTTPException

from assessments.scoring import (
    build_assessment_id,
    build_question_set_hash,
    rank_dimensions,
)
from holland.questions import (
    DIMENSION_LABELS,
    HOLLAND_ASSESSMENT_VERSION,
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
    missing_question_ids = [
        question.id for question in HOLLAND_QUESTIONS
        if question.id not in answered_by_id
    ]
    if missing_question_ids or len(answered_by_id) != len(request.answers):
        raise HTTPException(
            status_code=400,
            detail="Holland assessment requires exactly one answer for every question.",
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

    sorted_dimensions, tied_top_dimensions, score_margin = rank_dimensions(
        list(DIMENSION_LABELS.keys()),
        scores,
        raw_scores,
    )
    top_code = "-".join(sorted_dimensions[:3])
    top_dimension = sorted_dimensions[0]
    return HollandScoreResponse(
        status="success",
        assessment_id=build_assessment_id(
            user_id=request.user_id,
            assessment_type="holland",
            assessment_version=HOLLAND_ASSESSMENT_VERSION,
            answers=request.answers,
            attempt_id=request.attempt_id or request.session_id,
        ),
        assessment_version=HOLLAND_ASSESSMENT_VERSION,
        question_set_hash=build_question_set_hash(HOLLAND_QUESTIONS),
        user_id=request.user_id,
        session_id=request.session_id,
        attempt_id=request.attempt_id,
        scores=scores,
        raw_scores=raw_scores,
        top_code=top_code,
        tied_top_dimensions=tied_top_dimensions,
        score_margin=score_margin,
        interpretation_vi=INTERPRETATION_BY_TOP[top_dimension],
        answered_count=len(request.answers),
        missing_question_ids=missing_question_ids,
        created_at=utc_now(),
    )
