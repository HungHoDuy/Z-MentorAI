from typing import Optional

from pydantic import BaseModel


class ProfileRequest(BaseModel):
    user_id: str
    background_info: str = ""
    cv_document_id: Optional[str] = None


class ProfileResponse(BaseModel):
    status: str
    feature: str = "profile_scan"
    scan_status: str
    cv_document_id: Optional[str] = None
    message_vi: str
    next_status: str = "pending_extraction"
    parser_type: Optional[str] = None
    text_char_count: Optional[int] = None
    page_count: Optional[int] = None
    parsed_text_gcs_uri: Optional[str] = None
    parsed_result_gcs_uri: Optional[str] = None
    extracted_at: Optional[str] = None
    ocr_fallback_used: Optional[bool] = None
    target_role: Optional[str] = None
    benchmark_profile_id: Optional[str] = None
    benchmark_version: Optional[str] = None
    grade: Optional[str] = None
    total_score: Optional[float] = None
    score_dimensions: Optional[list[dict]] = None
    extracted_skills: Optional[list[str]] = None
    work_experiences: Optional[list[str]] = None
    education_records: Optional[list[str]] = None
    projects: Optional[list[str]] = None
    strengths: Optional[list[str]] = None
    weaknesses: Optional[list[str]] = None
    missing_signals: Optional[list[str]] = None
    recommendations: Optional[list[str]] = None
    benchmark_notes: Optional[list[str]] = None
    ai_extraction_used: Optional[bool] = None
    ai_extraction_confidence: Optional[float] = None
    structured_profile: Optional[dict] = None
    analysis_artifact_gcs_uri: Optional[str] = None
    analyzed_at: Optional[str] = None
