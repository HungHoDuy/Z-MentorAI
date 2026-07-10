import uuid
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
        raise RuntimeError("Firestore is required for canonical profiles.")
    return firestore_client


async def get_canonical_profile(user_id: str) -> Optional[dict]:
    client = require_firestore()
    snapshot = client.collection(settings.profiles_collection).document(user_id).get()
    return snapshot.to_dict() if snapshot.exists else None


async def save_profile_version(
    *,
    profile: dict,
    previous_profile: dict | None,
    cv_document_id: str,
) -> dict:
    client = require_firestore()
    profile_ref = client.collection(settings.profiles_collection).document(profile["user_id"])
    version_id = str(uuid.uuid4())
    version_ref = client.collection(settings.profile_versions_collection).document(version_id)
    current_cv_ref = client.collection(settings.cv_documents_collection).document(cv_document_id)
    batch = client.batch()

    version_payload = {
        **profile,
        "profile_version_id": version_id,
        "snapshot_type": "canonical_profile_version",
    }
    batch.set(version_ref, version_payload)
    batch.set(profile_ref, profile)
    batch.update(current_cv_ref, {
        "profile_link_status": "active",
        "profile_version": profile["profile_version"],
        "profile_version_id": version_id,
    })

    previous_cv_document_id = (previous_profile or {}).get("active_cv_document_id")
    if previous_cv_document_id and previous_cv_document_id != cv_document_id:
        previous_cv_ref = client.collection(settings.cv_documents_collection).document(
            previous_cv_document_id
        )
        batch.update(previous_cv_ref, {"profile_link_status": "superseded"})

    batch.commit()
    return {**profile, "profile_version_id": version_id}


async def mark_profile_decision(cv_document_id: str, updates: dict) -> None:
    client = require_firestore()
    client.collection(settings.cv_documents_collection).document(cv_document_id).update(updates)
