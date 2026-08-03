from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from cv_intake.schemas import CvIntakeResponse
from cv_intake.service import intake_cv_file
from cv_intake.repository import get_cv_document
from cv_intake.progress import processing_steps


router = APIRouter(prefix="/cv", tags=["cv-intake"])


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
        "processing_steps": processing_steps(stage),
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
