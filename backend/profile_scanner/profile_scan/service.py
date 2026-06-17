from fastapi import HTTPException

from cv_intake.repository import get_cv_document
from profile_scan.schemas import ProfileRequest, ProfileResponse


async def analyze_profile(request: ProfileRequest) -> ProfileResponse:
    if not request.cv_document_id:
        return ProfileResponse(
            status="success",
            scan_status="awaiting_cv_document",
            message_vi=(
                "Profile Scanner cần một CV đã được lưu trước khi phân tích hồ sơ. "
                "Vui lòng đính kèm CV để hệ thống lưu tài liệu và bắt đầu bước trích xuất."
            ),
        )

    document = await get_cv_document(request.cv_document_id)
    if not document or document.get("user_id") != request.user_id:
        raise HTTPException(status_code=404, detail="CV document not found for this user.")

    return ProfileResponse(
        status="success",
        scan_status="cv_intake_completed",
        cv_document_id=request.cv_document_id,
        message_vi=(
            "Profile Scanner đã nhận CV và lưu tài liệu an toàn. "
            "Bước tiếp theo là trích xuất nội dung CV, chuẩn hóa hồ sơ và đánh giá benchmark."
        ),
    )
