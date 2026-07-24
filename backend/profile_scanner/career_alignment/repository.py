from typing import Optional

from core.config import settings


firestore_client = None

if settings.use_firestore:
    from google.cloud import firestore

    if settings.firestore_database and settings.firestore_database != "(default)":
        firestore_client = firestore.Client(database=settings.firestore_database)
    else:
        firestore_client = firestore.Client()


def require_firestore():
    if not settings.use_firestore or firestore_client is None:
        raise RuntimeError("Firestore is required for career alignment results.")
    return firestore_client


async def save_alignment_result(result: dict) -> None:
    client = require_firestore()
    client.collection(settings.alignment_results_collection).document(result["user_id"]).set(result)


async def get_alignment_result(user_id: str) -> Optional[dict]:
    client = require_firestore()
    snapshot = client.collection(settings.alignment_results_collection).document(user_id).get()
    return snapshot.to_dict() if snapshot.exists else None
