from fastapi import HTTPException

from canonical_profile.service import prepare_profile_action
from cv_extraction.service import extract_cv_text
from cv_intake.repository import get_cv_document, get_latest_cv_document, update_cv_document
from profile_analysis.service import analyze_cv_profile
from profile_scan.schemas import ProfileRequest, ProfileResponse


def build_profile_response(document: dict, analysis, profile_action: dict | None = None) -> ProfileResponse:
    return ProfileResponse(
        status=analysis.status,
        scan_status=analysis.scan_status,
        cv_document_id=analysis.cv_document_id,
        message_vi=analysis.message_vi,
        next_status=(
            "profile_updated"
            if profile_action and profile_action.get("action_required") in {"auto_update_profile", "profile_current"}
            else "pending_profile_confirmation"
        ),
        parser_type=document.get("parser_type"),
        text_char_count=document.get("text_char_count"),
        page_count=document.get("page_count"),
        parsed_text_gcs_uri=document.get("parsed_text_gcs_uri"),
        parsed_result_gcs_uri=document.get("parsed_result_gcs_uri"),
        extracted_at=document.get("extracted_at"),
        ocr_fallback_used=document.get("ocr_fallback_used"),
        target_role=analysis.target_role,
        target_role_source=analysis.target_role_source,
        target_role_confidence=analysis.target_role_confidence,
        benchmark_status=analysis.benchmark_status,
        benchmark_profile_id=analysis.benchmark_profile_id,
        benchmark_version=analysis.benchmark_version,
        benchmark_type=analysis.benchmark_type,
        benchmark_confidence=analysis.benchmark_confidence,
        benchmark_confidence_score=analysis.benchmark_confidence_score,
        benchmark_sample_size=analysis.benchmark_sample_size,
        benchmark_distinct_companies=analysis.benchmark_distinct_companies,
        benchmark_sources=analysis.benchmark_sources,
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
        candidate_identity=analysis.candidate_identity,
        profile_action=profile_action,
        analysis_artifact_gcs_uri=analysis.analysis_artifact_gcs_uri,
        analyzed_at=analysis.analyzed_at,
    )


async def analyze_profile(request: ProfileRequest) -> ProfileResponse:
    document = None
    if request.cv_document_id:
        document = await get_cv_document(request.cv_document_id)
    else:
        document = await get_latest_cv_document(request.user_id)

    if not document:
        return ProfileResponse(
            status="success",
            scan_status="awaiting_cv_document",
            message_vi=(
                "Profile Scanner cần một CV đã được lưu trước khi phân tích hồ sơ. "
                "Vui lòng đính kèm CV để hệ thống lưu tài liệu và bắt đầu bước trích xuất."
            ),
        )

    if not document or document.get("user_id") != request.user_id:
        raise HTTPException(status_code=404, detail="CV document not found for this user.")

    cv_document_id = document["cv_document_id"]
    if request.target_role and request.target_role.strip() != (document.get("requested_target_role") or "").strip():
        await update_cv_document(cv_document_id, {
            "requested_target_role": request.target_role.strip(),
            "analysis_status": "pending",
            "next_status": "pending_profile_analysis",
        })
        document = await get_cv_document(cv_document_id)

    if document.get("extraction_status") != "completed":
        await extract_cv_text(document)
        document = await get_cv_document(cv_document_id)
        if not document:
            raise HTTPException(status_code=404, detail="CV document not found after extraction.")

    analysis = await analyze_cv_profile(document)
    profile_action = await prepare_profile_action(document, analysis.as_firestore_payload())
    return build_profile_response(document, analysis, profile_action)
