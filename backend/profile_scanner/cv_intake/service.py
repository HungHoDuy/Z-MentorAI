import datetime
import hashlib
import mimetypes
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from google.cloud import storage

from core.config import logger, settings
from cv_intake.repository import save_cv_document
from cv_intake.schemas import CvIntakeResponse


ALLOWED_EXTENSIONS = {"pdf", "docx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def normalize_user_path(user_id: str) -> str:
    safe_user_id = re.sub(r"[^a-zA-Z0-9._-]", "_", user_id.strip())
    if not safe_user_id:
        raise HTTPException(status_code=400, detail="user_id is required.")
    return safe_user_id


def get_extension(filename: str) -> str:
    extension = Path(filename or "").suffix.lower().lstrip(".")
    return extension


def resolve_mime_type(file: UploadFile, extension: str) -> str:
    guessed_type = mimetypes.guess_type(file.filename or "")[0]
    if file.content_type and file.content_type != "application/octet-stream":
        return file.content_type
    return guessed_type or file.content_type or "application/octet-stream"


def file_kind_from_extension(extension: str) -> str:
    return extension


async def intake_cv_file(
    *,
    file: UploadFile,
    user_id: str,
    session_id: str | None = None,
    target_role: str | None = None,
    message: str | None = None,
) -> CvIntakeResponse:
    if not settings.cv_storage_bucket:
        raise HTTPException(
            status_code=503,
            detail="CV_STORAGE_BUCKET is not configured for Profile Scanner.",
        )
    if not settings.use_firestore:
        raise HTTPException(
            status_code=503,
            detail="USE_FIRESTORE=true is required for CV intake metadata.",
        )

    original_filename = file.filename or "cv"
    extension = get_extension(original_filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported CV file type. Allowed: PDF or DOCX.",
        )

    content = await file.read()
    file_size = len(content)
    if file_size <= 0:
        raise HTTPException(status_code=400, detail="CV file is empty.")
    if file_size > settings.cv_max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"CV file is too large. Maximum size is {settings.cv_max_file_size_bytes} bytes.",
        )

    mime_type = resolve_mime_type(file, extension)
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported CV MIME type: {mime_type}.",
        )

    cv_document_id = str(uuid.uuid4())
    safe_user_id = normalize_user_path(user_id)
    object_name = f"users/{safe_user_id}/cv_documents/{cv_document_id}/original.{extension}"
    content_hash = hashlib.sha256(content).hexdigest()
    storage_uri = f"gs://{settings.cv_storage_bucket}/{object_name}"
    uploaded_at = utc_now()

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(settings.cv_storage_bucket)
        blob = bucket.blob(object_name)
        blob.upload_from_string(content, content_type=mime_type)
    except Exception as exc:
        logger.exception(
            "Failed to upload CV to GCS",
            extra={
                "user_id": user_id,
                "bucket": settings.cv_storage_bucket,
                "object_name": object_name,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to store CV file in Google Cloud Storage.",
        ) from exc

    document = {
        "cv_document_id": cv_document_id,
        "user_id": user_id,
        "session_id": session_id,
        "target_role": target_role,
        "message": message,
        "original_filename": original_filename,
        "mime_type": mime_type,
        "file_kind": file_kind_from_extension(extension),
        "file_size_bytes": file_size,
        "content_hash": content_hash,
        "storage_bucket": settings.cv_storage_bucket,
        "storage_object": object_name,
        "storage_uri": storage_uri,
        "uploaded_at": uploaded_at,
        "extraction_status": "pending",
        "next_status": "pending_extraction",
    }

    try:
        await save_cv_document(document)
    except Exception as exc:
        try:
            blob.delete()
        except Exception:
            logger.exception(
                "Failed to clean up CV object after metadata save failure",
                extra={
                    "cv_document_id": cv_document_id,
                    "bucket": settings.cv_storage_bucket,
                    "object_name": object_name,
                },
            )
        logger.exception(
            "Failed to save CV metadata",
            extra={
                "cv_document_id": cv_document_id,
                "user_id": user_id,
                "collection": settings.cv_documents_collection,
                "error_type": type(exc).__name__,
            },
        )
        raise HTTPException(
            status_code=503,
            detail="Unable to save CV metadata in Firestore.",
        ) from exc

    return CvIntakeResponse(
        status="success",
        cv_document_id=cv_document_id,
        user_id=user_id,
        original_filename=original_filename,
        mime_type=mime_type,
        file_kind=file_kind_from_extension(extension),
        file_size_bytes=file_size,
        content_hash=content_hash,
        storage_uri=storage_uri,
        uploaded_at=uploaded_at,
    )
