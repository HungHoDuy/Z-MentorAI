from typing import Optional

from core.config import settings


firestore_client = None

if settings.use_firestore:
    from google.cloud import firestore

    if settings.firestore_database and settings.firestore_database != "(default)":
        firestore_client = firestore.Client(database=settings.firestore_database)
    else:
        firestore_client = firestore.Client()


async def save_cv_document(document: dict) -> None:
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for CV document metadata.")

    firestore_client.collection(settings.cv_documents_collection).document(
        document["cv_document_id"]
    ).set(document)


async def get_cv_document(cv_document_id: str) -> Optional[dict]:
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for CV document metadata.")

    doc = firestore_client.collection(settings.cv_documents_collection).document(
        cv_document_id
    ).get()
    return doc.to_dict() if doc.exists else None

