from fastapi import HTTPException

from cv_extraction.service import extract_cv_text
from cv_intake.repository import get_cv_document
from profile_analysis.service import analyze_cv_profile
from profile_scan.schemas import ProfileRequest, ProfileResponse


def build_profile_response(document: dict, analysis) -> ProfileResponse:
    return ProfileResponse(
        status=analysis.status,
        scan_status=analysis.scan_status,
        cv_document_id=analysis.cv_document_id,
        message_vi=analysis.message_vi,
        next_status="analysis_completed",
        parser_type=document.get("parser_type"),
        text_char_count=document.get("text_char_count"),
        page_count=document.get("page_count"),
        parsed_text_gcs_uri=document.get("parsed_text_gcs_uri"),
        parsed_result_gcs_uri=document.get("parsed_result_gcs_uri"),
        extracted_at=document.get("extracted_at"),
        ocr_fallback_used=document.get("ocr_fallback_used"),
        target_role=analysis.target_role,
        benchmark_profile_id=analysis.benchmark_profile_id,
        benchmark_version=analysis.benchmark_version,
        grade=analysis.grade,
        total_score=analysis.total_score,
        score_dimensions=[dimension.model_dump(mode="json") for dimension in analysis.score_dimensions],
        extracted_skills=analysis.extracted_skills,
        work_experiences=analysis.work_experiences,
        education_records=analysis.education_records,
        projects=analysis.projects,
        strengths=analysis.strengths,
        weaknesses=analysis.weaknesses,
        missing_signals=analysis.missing_signals,
        recommendations=analysis.recommendations,
        benchmark_notes=analysis.benchmark_notes,
        ai_extraction_used=analysis.ai_extraction_used,
        ai_extraction_confidence=analysis.ai_extraction_confidence,
        structured_profile=analysis.structured_profile,
        analysis_artifact_gcs_uri=analysis.analysis_artifact_gcs_uri,
        analyzed_at=analysis.analyzed_at,
    )


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

    if document.get("extraction_status") != "completed":
        await extract_cv_text(document)
        document = await get_cv_document(request.cv_document_id)
        if not document:
            raise HTTPException(status_code=404, detail="CV document not found after extraction.")

    analysis = await analyze_cv_profile(document)
    return build_profile_response(document, analysis)
