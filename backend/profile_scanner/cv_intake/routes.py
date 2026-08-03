from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from cv_intake.schemas import CvIntakeResponse
from cv_intake.service import intake_cv_file
from cv_intake.repository import get_cv_document


router = APIRouter(prefix="/cv", tags=["cv-intake"])


PROCESSING_STAGES = [
    ("extracting_cv", "Trích xuất nội dung CV"),
    ("draft_ready", "Tạo CV Draft"),
    ("awaiting_target_level", "Xác định cấp độ mục tiêu"),
    ("draft_confirmed", "Xác nhận CV Draft"),
    ("analyzing_profile", "Chuẩn hóa hồ sơ đã xác nhận"),
    ("loading_benchmark", "Tải benchmark vai trò và cấp độ"),
    ("scoring_profile", "Chấm điểm theo bằng chứng"),
    ("building_feedback", "Tạo nhận xét cải thiện"),
    ("preparing_canonical_profile", "Chuẩn bị hồ sơ cá nhân"),
    ("completed", "Hoàn tất đánh giá"),
]


def _processing_steps(current_stage: str) -> list[dict]:
    stage_keys = [key for key, _ in PROCESSING_STAGES]
    current_index = stage_keys.index(current_stage) if current_stage in stage_keys else -1
    waiting_stages = {"draft_ready", "awaiting_target_level"}
    return [
        {
            "key": key,
            "label_vi": label,
            "status": (
                "completed" if index < current_index or current_stage == "completed"
                else "waiting_user" if key == current_stage and current_stage in waiting_stages
                else "running" if key == current_stage
                else "pending"
            ),
        }
        for index, (key, label) in enumerate(PROCESSING_STAGES)
    ]


@router.get("/{cv_document_id}/status")
async def get_cv_processing_status(cv_document_id: str, user_id: str):
    document = await get_cv_document(cv_document_id)
    if not document or document.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="CV document not found for this user.")
    stage = document.get("processing_stage") or "pending"
    return {
        "status": document.get("processing_status") or "pending",
        "feature": "cv_processing_progress",
        "cv_document_id": cv_document_id,
        "processing_stage": stage,
        "processing_steps": _processing_steps(stage),
        "error": document.get("processing_error"),
    }


@router.post("/intake", response_model=CvIntakeResponse)
async def intake_cv(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    session_id: Optional[str] = Form(None),
    target_role: Optional[str] = Form(None),
    message: Optional[str] = Form(None),
):
    return await intake_cv_file(
        file=file,
        user_id=user_id,
        session_id=session_id,
        target_role=target_role,
        message=message,
    )
