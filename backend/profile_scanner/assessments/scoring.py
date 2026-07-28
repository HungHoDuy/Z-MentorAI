import hashlib
import json
import uuid
from typing import Any


def build_question_set_hash(questions: list[Any]) -> str:
    payload = [
        {
            "id": question.id,
            "dimension": question.dimension,
            "text_vi": question.text_vi,
        }
        for question in questions
    ]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def build_assessment_id(
    *,
    user_id: str,
    assessment_type: str,
    assessment_version: str,
    answers: list[Any],
    attempt_id: str | None = None,
) -> str:
    normalized_answers = sorted(
        (
            {
                "question_id": answer.question_id,
                "score": answer.score,
            }
            for answer in answers
        ),
        key=lambda item: item["question_id"],
    )
    payload = json.dumps(
        {
            "user_id": user_id,
            "assessment_type": assessment_type,
            "assessment_version": assessment_version,
            "attempt_id": attempt_id or "",
            "answers": normalized_answers,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"z-mentorai:assessment:{payload}"))


def rank_dimensions(
    dimension_order: list[str],
    scores: dict[str, float],
    raw_scores: dict[str, int],
) -> tuple[list[str], list[str], float | None]:
    order_index = {dimension: index for index, dimension in enumerate(dimension_order)}
    ranked = sorted(
        dimension_order,
        key=lambda dimension: (
            -scores[dimension],
            -raw_scores[dimension],
            order_index[dimension],
        ),
    )
    top_score = scores[ranked[0]]
    tied_top = [
        dimension
        for dimension in ranked
        if scores[dimension] == top_score
    ]
    score_margin = (
        round(scores[ranked[0]] - scores[ranked[1]], 4)
        if len(ranked) > 1
        else None
    )
    return ranked, tied_top, score_margin
