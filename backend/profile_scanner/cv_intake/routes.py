from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from cv_intake.schemas import CvIntakeResponse
from cv_intake.service import intake_cv_file


router = APIRouter(prefix="/cv", tags=["cv-intake"])


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
