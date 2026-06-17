from pydantic import BaseModel


class CvIntakeResponse(BaseModel):
    status: str
    feature: str = "cv_intake"
    cv_document_id: str
    user_id: str
    original_filename: str
    mime_type: str
    file_kind: str
    file_size_bytes: int
    content_hash: str
    storage_uri: str
    uploaded_at: str
    next_status: str = "pending_extraction"

