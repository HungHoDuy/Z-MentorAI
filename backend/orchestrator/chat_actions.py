import json
from typing import Any, Optional

from fastapi import HTTPException


def build_structured_tool_request(
    action: Optional[dict[str, Any]],
    user_id: str,
) -> Optional[dict[str, Any]]:
    if not action:
        return None

    action_type = str(action.get("type") or "").strip().lower()
    if action_type == "profile.save_decision":
        cv_document_id = str(action.get("cv_document_id") or "").strip()
        decision = str(action.get("decision") or "").strip().lower()
        if not cv_document_id or decision not in {"accept", "update", "overwrite", "reject"}:
            raise HTTPException(status_code=400, detail="cv_document_id and a valid profile decision are required.")
        return {
            "tool": "profile_scanner",
            "input": {
                "user_id": user_id,
                "task": "profile_confirm",
                "cv_document_id": cv_document_id,
                "decision": decision,
            },
        }

    if action_type in {
        "cv_draft.confirm",
        "cv_draft.edit_requested",
        "cv_draft.apply_edit",
        "target_level.select",
    }:
        cv_document_id = str(action.get("cv_document_id") or "").strip()
        extraction_id = str(action.get("extraction_id") or "").strip()
        if not cv_document_id or not extraction_id:
            raise HTTPException(status_code=400, detail="cv_document_id and extraction_id are required.")
        task_by_action = {
            "cv_draft.confirm": "cv_draft_confirm",
            "cv_draft.edit_requested": "cv_draft_edit_requested",
            "cv_draft.apply_edit": "cv_draft_apply_edit",
            "target_level.select": "target_level_select",
        }
        tool_input = {
            "user_id": user_id,
            "task": task_by_action[action_type],
            "cv_document_id": cv_document_id,
            "extraction_id": extraction_id,
        }
        if action_type == "cv_draft.apply_edit":
            instruction = str(action.get("instruction") or "").strip()
            if not instruction:
                raise HTTPException(status_code=400, detail="CV draft edit instruction is required.")
            tool_input["edit_instruction"] = instruction
        if action_type == "target_level.select":
            target_level = str(action.get("target_level") or "").strip()
            if not target_level:
                raise HTTPException(status_code=400, detail="Target level is required.")
            tool_input["target_level"] = target_level
        return {"tool": "profile_scanner", "input": tool_input}

    if action_type != "assessment.submit":
        raise HTTPException(status_code=400, detail=f"Unsupported chat action: {action_type or 'missing'}")

    assessment_type = str(action.get("assessment_type") or "").strip().lower()
    answers = action.get("answers")
    if not isinstance(answers, list) or not answers:
        raise HTTPException(status_code=400, detail="Assessment answers are required.")

    normalized_answers = []
    for answer in answers:
        if not isinstance(answer, dict):
            raise HTTPException(status_code=400, detail="Each assessment answer must be an object.")
        question_id = str(answer.get("question_id") or "").strip()
        score = answer.get("score")
        if not question_id or not isinstance(score, int) or isinstance(score, bool) or score < 1 or score > 5:
            raise HTTPException(status_code=400, detail="Each assessment answer requires question_id and score from 1 to 5.")
        normalized_answers.append({"question_id": question_id, "score": score})

    is_holland = assessment_type in {"holland", "holland_riasec", "riasec"}
    return {
        "tool": "profile_scanner",
        "input": {
            "user_id": user_id,
            "task": "holland_score" if is_holland else "assessment_score",
            "assessment_type": "" if is_holland else assessment_type,
            "attempt_id": str(action.get("attempt_id") or ""),
            "question_set_hash": str(action.get("question_set_hash") or ""),
            "answers_json": json.dumps(normalized_answers, ensure_ascii=False),
        },
    }
