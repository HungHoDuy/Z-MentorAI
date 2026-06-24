from pydantic import BaseModel


class CvExtractionResult(BaseModel):
    status: str = "success"
    scan_status: str = "extraction_completed"
    cv_document_id: str
    parser_type: str
    ocr_fallback_used: bool = False
    text_char_count: int
    page_count: int | None = None
    parsed_text_gcs_uri: str
    parsed_result_gcs_uri: str
    extracted_at: str
    message_vi: str
