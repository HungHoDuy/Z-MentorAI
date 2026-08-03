import datetime
import uuid

from fastapi import HTTPException

from canonical_profile.service import prepare_profile_action
from cv_draft.repository import confirm_cv_draft, get_cv_draft
from cv_draft.service import get_or_create_cv_draft, revise_cv_draft
from cv_extraction.service import EXTRACTION_VERSION, extract_cv_text
from cv_intake.repository import (
    claim_cv_processing,
    get_cv_document,
    get_latest_cv_document,
    update_cv_document,
)
from cv_intake.progress import processing_steps
from profile_analysis.service import analyze_cv_profile
from profile_analysis.levels import infer_current_level, level_options, normalize_target_level
from profile_ai_extraction.schemas import StructuredProfile
from profile_scan.schemas import ProfileRequest, ProfileResponse


def build_profile_response(document: dict, analysis, profile_action: dict | None = None) -> ProfileResponse:
    return ProfileResponse(
        status=analysis.status,
        scan_status=analysis.scan_status,
        cv_document_id=analysis.cv_document_id,
        message_vi=analysis.message_vi,
        next_status="pending_profile_confirmation" if profile_action else "completed",
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
        target_level=analysis.target_level,
        target_level_source=analysis.target_level_source,
        benchmark_status=analysis.benchmark_status,
        benchmark_profile_id=analysis.benchmark_profile_id,
        benchmark_version=analysis.benchmark_version,
        benchmark_type=analysis.benchmark_type,
        benchmark_confidence=analysis.benchmark_confidence,
        benchmark_confidence_score=analysis.benchmark_confidence_score,
        benchmark_sample_size=analysis.benchmark_sample_size,
        benchmark_distinct_companies=analysis.benchmark_distinct_companies,
        benchmark_sources=analysis.benchmark_sources,
        benchmark_snapshot=analysis.benchmark_snapshot,
        grade=analysis.grade,
        total_score=analysis.total_score,
        score_dimensions=[dimension.model_dump(mode="json") for dimension in analysis.score_dimensions],
        extracted_skills=analysis.extracted_skills,
        normalized_skills=analysis.normalized_skills,
        skill_normalization_version=analysis.skill_normalization_version,
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
        processing_steps=processing_steps("completed"),
    )


def build_draft_response(document: dict, draft: dict) -> ProfileResponse:
    profile = StructuredProfile(**draft["structured_profile"])
    current_level, level_confidence, level_evidence = infer_current_level(profile)
    profile_payload = profile.as_firestore_payload()
    profile_issues = list(profile_payload.get("profile_issues") or [])
    existing_issue_fields = {issue.get("field") for issue in profile_issues if isinstance(issue, dict)}
    for field in ("email", "phone", "location"):
        if not getattr(profile, field) and field not in existing_issue_fields:
            profile_issues.append({"field": field, "code": "missing", "severity": "warning"})
    profile_payload["profile_issues"] = profile_issues
    return ProfileResponse(
        status="success",
        feature="cv_draft",
        scan_status="draft_ready",
        cv_document_id=document["cv_document_id"],
        extraction_id=draft["extraction_id"],
        draft_status=draft.get("status", "draft"),
        draft_version=draft.get("version", 1),
        cv_draft=profile_payload,
        message_vi="Hệ thống đã đọc CV. Vui lòng kiểm tra hồ sơ được nhận diện trước khi đánh giá.",
        next_status="pending_draft_confirmation",
        parser_type=document.get("parser_type"),
        text_char_count=document.get("text_char_count"),
        page_count=document.get("page_count"),
        ocr_fallback_used=document.get("ocr_fallback_used"),
        target_role=document.get("requested_target_role") or profile.target_role_hint or None,
        current_level_estimate=current_level,
        current_level_confidence=level_confidence,
        current_level_evidence=level_evidence,
        available_actions=[
            {"type": "cv_draft.confirm", "label_vi": "Xác nhận thông tin và đánh giá"},
            {"type": "cv_draft.edit_requested", "label_vi": "Chỉnh sửa thông tin"},
        ],
        processing_steps=processing_steps("draft_ready"),
    )


def build_level_confirmation_response(document: dict, draft: dict) -> ProfileResponse:
    profile = StructuredProfile(**draft["structured_profile"])
    current_level, level_confidence, level_evidence = infer_current_level(profile)
    return ProfileResponse(
        status="success",
        feature="target_level_confirmation",
        scan_status="awaiting_target_level",
        cv_document_id=document["cv_document_id"],
        extraction_id=draft["extraction_id"],
        draft_status=draft.get("status"),
        draft_version=draft.get("version", 1),
        target_role=document.get("requested_target_role") or profile.target_role_hint or None,
        current_level_estimate=current_level,
        current_level_confidence=level_confidence,
        current_level_evidence=level_evidence,
        level_options=level_options(),
        message_vi=(
            "CV chưa nêu rõ cấp độ mục tiêu. Hãy chọn cấp độ bạn muốn ứng tuyển để hệ thống dùng tiêu chí đánh giá phù hợp."
        ),
        next_status="pending_target_level",
        processing_steps=processing_steps("awaiting_target_level"),
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
    operation = (request.operation or "extract_draft").strip().lower()
    allowed_operations = {"extract_draft", "confirm_draft", "apply_draft_edit", "select_target_level"}
    if operation not in allowed_operations:
        raise HTTPException(status_code=400, detail=f"Unsupported profile scan operation: {operation}")

    processing_attempt_id = str(uuid.uuid4())
    claimed = await claim_cv_processing(cv_document_id, processing_attempt_id)
    if not claimed:
        raise HTTPException(
            status_code=409,
            detail="This CV is already being processed. Please retry shortly.",
        )
    try:
        if request.target_role and request.target_role.strip() != (document.get("requested_target_role") or "").strip():
            await update_cv_document(cv_document_id, {
                "requested_target_role": request.target_role.strip(),
                "analysis_status": "pending",
                "next_status": "pending_profile_analysis",
            })
            document = await get_cv_document(cv_document_id)

        normalized_target_level = normalize_target_level(request.target_level)
        if request.target_level and not normalized_target_level:
            raise HTTPException(status_code=400, detail="Unsupported target level.")
        if normalized_target_level and normalized_target_level != document.get("requested_target_level"):
            await update_cv_document(cv_document_id, {
                "requested_target_level": normalized_target_level,
                "analysis_status": "pending",
                "next_status": "pending_profile_analysis",
            })
            document = await get_cv_document(cv_document_id)

        if (
            document.get("extraction_status") != "completed"
            or document.get("extraction_version") != EXTRACTION_VERSION
        ):
            await update_cv_document(cv_document_id, {
                "processing_stage": "extracting_cv",
                "processing_stage_updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            await extract_cv_text(document)
            document = await get_cv_document(cv_document_id)
            if not document:
                raise HTTPException(status_code=404, detail="CV document not found after extraction.")

        draft = None
        if request.extraction_id:
            draft = await get_cv_draft(request.extraction_id)
            if not draft or draft.get("user_id") != request.user_id or draft.get("cv_document_id") != cv_document_id:
                raise HTTPException(status_code=404, detail="CV draft not found for this user.")
        else:
            draft = await get_or_create_cv_draft(document)

        if operation == "apply_draft_edit":
            draft = await revise_cv_draft(draft, request.edit_instruction or "")
            document = await get_cv_document(cv_document_id)

        if operation == "extract_draft":
            await update_cv_document(cv_document_id, {
                "processing_status": "awaiting_user",
                "processing_stage": "draft_ready",
                "processing_attempt_id": processing_attempt_id,
                "processing_finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "processing_error": None,
            })
            return build_draft_response(document, draft)

        profile = StructuredProfile(**draft["structured_profile"])
        explicit_level = (
            normalize_target_level(document.get("requested_target_level"))
            or normalize_target_level(document.get("requested_target_role"))
            or normalize_target_level(profile.target_role_hint)
        )
        if not explicit_level:
            await update_cv_document(cv_document_id, {
                "processing_status": "awaiting_user",
                "processing_stage": "awaiting_target_level",
                "processing_finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            })
            return build_level_confirmation_response(document, draft)
        if document.get("requested_target_level") != explicit_level:
            await update_cv_document(cv_document_id, {"requested_target_level": explicit_level})
            document = await get_cv_document(cv_document_id)

        confirmed_draft = await confirm_cv_draft(draft["extraction_id"], request.user_id)
        await update_cv_document(cv_document_id, {
            "processing_stage": "analyzing_profile",
            "processing_stage_updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        analysis = await analyze_cv_profile(
            document,
            StructuredProfile(**confirmed_draft["structured_profile"]),
        )
        await update_cv_document(cv_document_id, {
            "processing_stage": "preparing_canonical_profile",
            "processing_stage_updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })
        profile_action = await prepare_profile_action(document, analysis.as_firestore_payload())
        await update_cv_document(cv_document_id, {
            "processing_status": "completed",
            "processing_stage": "completed",
            "processing_attempt_id": processing_attempt_id,
            "processing_finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "processing_error": None,
        })
        return build_profile_response(document, analysis, profile_action)
    except Exception as exc:
        try:
            await update_cv_document(cv_document_id, {
                "processing_status": "failed",
                "processing_stage": "failed",
                "processing_attempt_id": processing_attempt_id,
                "processing_finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "processing_error": str(exc)[:500],
            })
        except Exception:
            # Preserve the original pipeline failure; request middleware logs the traceback.
            pass
        raise
