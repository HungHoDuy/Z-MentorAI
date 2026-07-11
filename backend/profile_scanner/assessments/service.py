import datetime
import uuid
from collections import defaultdict

from fastapi import HTTPException

from assessments.definitions import ASSESSMENT_DEFINITIONS, AssessmentDefinition
from assessments.schemas import AssessmentScoreRequest, AssessmentScoreResponse


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def get_assessment_definition(assessment_type: str) -> AssessmentDefinition:
    normalized_type = (assessment_type or "").strip().lower()
    definition = ASSESSMENT_DEFINITIONS.get(normalized_type)
    if not definition:
        raise HTTPException(
            status_code=404,
            detail=f"Unsupported assessment type: {assessment_type}",
        )
    return definition


def score_assessment_answers(
    assessment_type: str,
    request: AssessmentScoreRequest,
) -> AssessmentScoreResponse:
    definition = get_assessment_definition(assessment_type)
    question_by_id = {question.id: question for question in definition.questions}
    answered_by_id = {answer.question_id: answer for answer in request.answers}
    unknown_ids = sorted(set(answered_by_id) - set(question_by_id))
    if unknown_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown assessment question ids: {', '.join(unknown_ids)}",
        )

    raw_scores = {dimension: 0 for dimension in definition.dimension_labels}
    counts = defaultdict(int)
    for answer in request.answers:
        question = question_by_id[answer.question_id]
        raw_scores[question.dimension] += answer.score
        counts[question.dimension] += 1

    scores = {}
    for dimension in definition.dimension_labels:
        max_score = max(counts[dimension] * 5, 1)
        scores[dimension] = round(raw_scores[dimension] / max_score, 2)

    sorted_dimensions = sorted(
        definition.dimension_labels.keys(),
        key=lambda dimension: (scores[dimension], raw_scores[dimension], dimension),
        reverse=True,
    )
    top_dimensions = sorted_dimensions[:3]
    top_dimension = top_dimensions[0]
    missing_question_ids = [
        question.id for question in definition.questions
        if question.id not in answered_by_id
    ]
    recommendations = []
    for dimension in top_dimensions:
        recommendations.extend(definition.recommendations_by_dimension.get(dimension, []))

    return AssessmentScoreResponse(
        status="success",
        assessment_id=str(uuid.uuid4()),
        assessment_type=definition.assessment_type,
        assessment_version=definition.version,
        user_id=request.user_id,
        session_id=request.session_id,
        scores=scores,
        raw_scores=raw_scores,
        top_dimensions=top_dimensions,
        result_code=" / ".join(top_dimensions),
        result_label_vi=definition.result_label_vi,
        interpretation_vi=definition.interpretation_by_dimension[top_dimension],
        recommendations_vi=recommendations[:5],
        answered_count=len(request.answers),
        missing_question_ids=missing_question_ids,
        created_at=utc_now(),
    )
