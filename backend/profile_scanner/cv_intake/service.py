import datetime
import hashlib
import io
import mimetypes
import re
import uuid
import zipfile
from pathlib import Path

from fastapi import HTTPException, UploadFile
from google.api_core.exceptions import AlreadyExists, PreconditionFailed
from google.cloud import storage

from core.config import logger, settings
from cv_intake.repository import (
    get_cv_document,
    get_cv_document_by_user_hash,
    save_cv_document,
    update_cv_document,
)
from cv_intake.schemas import CvIntakeResponse


ALLOWED_EXTENSIONS = {"pdf", "docx"}
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_DOCX_ARCHIVE_ENTRIES = 2000
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024


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


def validate_file_signature(content: bytes, extension: str) -> None:
    if extension == "pdf":
        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is not a valid PDF document.",
            )
        lowered = content.lower()
        if any(marker in lowered for marker in (b"/javascript", b"/launch", b"/embeddedfile")):
            raise HTTPException(
                status_code=400,
                detail="PDF files containing active or embedded content are not supported.",
            )
        return

    if extension == "docx":
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                members = archive.infolist()
                names = {member.filename for member in members}
        except (zipfile.BadZipFile, OSError) as exc:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is not a valid DOCX document.",
            ) from exc
        uncompressed_size = sum(member.file_size for member in members)
        if (
            len(members) > MAX_DOCX_ARCHIVE_ENTRIES
            or uncompressed_size > MAX_DOCX_UNCOMPRESSED_BYTES
        ):
            raise HTTPException(
                status_code=400,
                detail="The DOCX archive expands beyond the supported safety limit.",
            )
        required_parts = {"[Content_Types].xml", "word/document.xml"}
        if not required_parts.issubset(names):
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is not a valid DOCX document.",
            )
        if any(
            name.casefold().endswith(("vbaproject.bin", ".exe", ".dll", ".js"))
            for name in names
        ):
            raise HTTPException(
                status_code=400,
                detail="DOCX files containing active or executable content are not supported.",
            )


def deterministic_cv_document_id(user_id: str, content_hash: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"z-mentorai:cv:{user_id}:{content_hash}"))


def build_intake_response(document: dict) -> CvIntakeResponse:
    return CvIntakeResponse(
        status="success",
        cv_document_id=document["cv_document_id"],
        user_id=document["user_id"],
        original_filename=document["original_filename"],
        mime_type=document["mime_type"],
        file_kind=document["file_kind"],
        file_size_bytes=document["file_size_bytes"],
        content_hash=document["content_hash"],
        storage_uri=document["storage_uri"],
        uploaded_at=document["uploaded_at"],
    )


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

    validate_file_signature(content, extension)
    mime_type = resolve_mime_type(file, extension)
    expected_mime_type = (
        "application/pdf"
        if extension == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    if mime_type not in ALLOWED_MIME_TYPES and mime_type != "application/octet-stream":
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported CV MIME type: {mime_type}.",
        )
    mime_type = expected_mime_type

    content_hash = hashlib.sha256(content).hexdigest()
    existing_document = await get_cv_document_by_user_hash(user_id, content_hash)
    if existing_document:
        updates = {}
        if target_role and target_role.strip() != (existing_document.get("requested_target_role") or "").strip():
            updates.update({
                "requested_target_role": target_role.strip(),
                "target_role": target_role.strip(),
                "analysis_status": "pending",
                "next_status": "pending_profile_analysis",
            })
        if session_id:
            updates["session_id"] = session_id
        if message:
            updates["message"] = message
        if updates:
            await update_cv_document(existing_document["cv_document_id"], updates)
            existing_document.update(updates)
        logger.info(
            "Reused idempotent CV upload",
            extra={
                "user_id": user_id,
                "cv_document_id": existing_document["cv_document_id"],
                "content_hash": content_hash,
            },
        )
        return build_intake_response(existing_document)

    cv_document_id = deterministic_cv_document_id(user_id, content_hash)
    safe_user_id = normalize_user_path(user_id)
    object_name = f"users/{safe_user_id}/cv_documents/{cv_document_id}/original.{extension}"
    storage_uri = f"gs://{settings.cv_storage_bucket}/{object_name}"
    uploaded_at = utc_now()

    object_created = False
    uploaded_generation = None
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(settings.cv_storage_bucket)
        blob = bucket.blob(object_name)
        blob.upload_from_string(
            content,
            content_type=mime_type,
            if_generation_match=0,
        )
        object_created = True
        uploaded_generation = int(blob.generation) if blob.generation is not None else None
    except PreconditionFailed:
        logger.info(
            "CV object already exists for idempotency key",
            extra={
                "user_id": user_id,
                "cv_document_id": cv_document_id,
                "object_name": object_name,
            },
        )
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
        "requested_target_role": target_role,
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
    except AlreadyExists:
        concurrent_document = await get_cv_document(cv_document_id)
        if concurrent_document:
            return build_intake_response(concurrent_document)
        raise HTTPException(
            status_code=409,
            detail="CV upload already exists but its metadata could not be loaded.",
        )
    except Exception as exc:
        try:
            concurrent_document = await get_cv_document(cv_document_id)
        except Exception:
            concurrent_document = None
        if concurrent_document:
            return build_intake_response(concurrent_document)
        if object_created and uploaded_generation is not None:
            try:
                blob.delete(if_generation_match=uploaded_generation)
            except Exception:
                logger.exception(
                    "Failed to clean up owned CV object generation after metadata save failure",
                    extra={
                        "cv_document_id": cv_document_id,
                        "bucket": settings.cv_storage_bucket,
                        "object_name": object_name,
                        "generation": uploaded_generation,
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

    return build_intake_response(document)
