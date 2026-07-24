import datetime
from typing import Optional

from core.config import settings


firestore_client = None

if settings.use_firestore:
    from google.cloud import firestore
    from google.cloud.firestore_v1.base_query import FieldFilter

    if settings.firestore_database and settings.firestore_database != "(default)":
        firestore_client = firestore.Client(database=settings.firestore_database)
    else:
        firestore_client = firestore.Client()


async def save_cv_document(document: dict) -> None:
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for CV document metadata.")

    firestore_client.collection(settings.cv_documents_collection).document(
        document["cv_document_id"]
    ).create(document)


async def get_cv_document(cv_document_id: str) -> Optional[dict]:
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for CV document metadata.")

    doc = firestore_client.collection(settings.cv_documents_collection).document(
        cv_document_id
    ).get()
    return doc.to_dict() if doc.exists else None


async def get_latest_cv_document(user_id: str) -> Optional[dict]:
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for CV document metadata.")
    docs = (
        firestore_client.collection(settings.cv_documents_collection)
        .where(filter=FieldFilter("user_id", "==", user_id))
        .order_by("uploaded_at", direction="DESCENDING")
        .limit(50)
        .stream()
    )
    for doc in docs:
        data = doc.to_dict() or {}
        if data.get("profile_link_status") in {"rejected", "superseded"}:
            continue
        if data.get("extraction_status") == "failed":
            continue
        return data
    return None


async def get_cv_document_by_user_hash(user_id: str, content_hash: str) -> Optional[dict]:
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for CV document metadata.")

    docs = (
        firestore_client.collection(settings.cv_documents_collection)
        .where(filter=FieldFilter("user_id", "==", user_id))
        .where(filter=FieldFilter("content_hash", "==", content_hash))
        .limit(5)
        .stream()
    )
    matches = [doc.to_dict() or {} for doc in docs]
    if not matches:
        return None
    return max(matches, key=lambda item: item.get("uploaded_at", ""))


async def update_cv_document(cv_document_id: str, updates: dict) -> None:
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for CV document metadata.")

    firestore_client.collection(settings.cv_documents_collection).document(
        cv_document_id
    ).update(updates)


async def claim_cv_processing(
    cv_document_id: str,
    attempt_id: str,
    lease_seconds: int = 900,
) -> bool:
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for CV processing.")

    document_ref = firestore_client.collection(settings.cv_documents_collection).document(
        cv_document_id
    )
    transaction = firestore_client.transaction()

    @firestore.transactional
    def claim(transaction):
        snapshot = document_ref.get(transaction=transaction)
        if not snapshot.exists:
            return False
        data = snapshot.to_dict() or {}
        started_at = data.get("processing_started_at")
        if isinstance(started_at, str):
            try:
                started_at = datetime.datetime.fromisoformat(started_at.replace("Z", "+00:00"))
            except ValueError:
                started_at = None
        if isinstance(started_at, datetime.datetime) and not started_at.tzinfo:
            started_at = started_at.replace(tzinfo=datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        lease_active = (
            data.get("processing_status") == "running"
            and started_at is not None
            and (now - started_at).total_seconds() < lease_seconds
            and data.get("processing_attempt_id") != attempt_id
        )
        if lease_active:
            return False
        transaction.update(document_ref, {
            "processing_status": "running",
            "processing_attempt_id": attempt_id,
            "processing_started_at": now.isoformat(),
            "processing_error": None,
        })
        return True

    return bool(claim(transaction))

