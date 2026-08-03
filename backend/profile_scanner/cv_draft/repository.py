import datetime
import uuid
from typing import Optional

from core.config import settings
from cv_intake.repository import firestore_client, update_cv_document


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


async def create_cv_draft(
    *,
    user_id: str,
    cv_document_id: str,
    structured_profile: dict,
    source: str,
    parent_extraction_id: str | None = None,
    edit_instruction: str | None = None,
) -> dict:
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for CV draft storage.")

    extraction_id = str(uuid.uuid4())
    now = utc_now()
    payload = {
        "extraction_id": extraction_id,
        "user_id": user_id,
        "cv_document_id": cv_document_id,
        "version": 1,
        "status": "draft",
        "source": source,
        "parent_extraction_id": parent_extraction_id,
        "edit_instruction": edit_instruction,
        "structured_profile": structured_profile,
        "created_at": now,
        "updated_at": now,
        "confirmed_at": None,
    }
    if parent_extraction_id:
        parent = await get_cv_draft(parent_extraction_id)
        payload["version"] = int((parent or {}).get("version", 0)) + 1

    firestore_client.collection(settings.cv_extractions_collection).document(
        extraction_id
    ).create(payload)
    await update_cv_document(cv_document_id, {
        "current_extraction_id": extraction_id,
        "draft_status": "draft",
        "processing_stage": "draft_ready",
        "processing_stage_updated_at": now,
    })
    return payload


async def get_cv_draft(extraction_id: str) -> Optional[dict]:
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for CV draft storage.")
    snapshot = firestore_client.collection(settings.cv_extractions_collection).document(
        extraction_id
    ).get()
    return snapshot.to_dict() if snapshot.exists else None


async def confirm_cv_draft(extraction_id: str, user_id: str) -> dict:
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for CV draft storage.")
    draft = await get_cv_draft(extraction_id)
    if not draft or draft.get("user_id") != user_id:
        raise ValueError("CV draft not found for this user.")
    now = utc_now()
    firestore_client.collection(settings.cv_extractions_collection).document(
        extraction_id
    ).update({"status": "confirmed", "confirmed_at": now, "updated_at": now})
    await update_cv_document(draft["cv_document_id"], {
        "current_extraction_id": extraction_id,
        "confirmed_extraction_id": extraction_id,
        "draft_status": "confirmed",
        "processing_stage": "draft_confirmed",
        "processing_stage_updated_at": now,
    })
    return {**draft, "status": "confirmed", "confirmed_at": now, "updated_at": now}
