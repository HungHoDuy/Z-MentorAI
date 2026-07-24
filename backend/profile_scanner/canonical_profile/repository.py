import uuid
from typing import Optional

from core.config import settings


firestore_client = None
firestore = None

if settings.use_firestore:
    from google.cloud import firestore as firestore_module

    firestore = firestore_module

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
    current_cv_ref = client.collection(settings.cv_documents_collection).document(cv_document_id)

    @firestore.transactional
    def commit_profile(transaction):
        current_snapshot = profile_ref.get(transaction=transaction)
        current_profile = current_snapshot.to_dict() if current_snapshot.exists else {}

        if (
            current_profile.get("active_cv_document_id") == cv_document_id
            and current_profile.get("analysis_fingerprint") == profile.get("analysis_fingerprint")
        ):
            return {
                **current_profile,
                "profile_version_id": current_profile.get("profile_version_id"),
            }

        predecessor_id = (
            current_profile.get("profile_version_id")
            or f"root-{current_profile.get('profile_version', 0)}"
        )
        operation_key = (
            f"{profile['user_id']}:{cv_document_id}:"
            f"{profile.get('analysis_fingerprint') or profile.get('updated_at') or ''}:"
            f"{predecessor_id}"
        )
        version_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"z-mentorai:profile:{operation_key}"))
        version_ref = client.collection(settings.profile_versions_collection).document(version_id)
        version_snapshot = version_ref.get(transaction=transaction)

        source_document_ids = list(current_profile.get("source_document_ids", []))
        if cv_document_id not in source_document_ids:
            source_document_ids.append(cv_document_id)
        current_version = int(current_profile.get("profile_version", 0))
        if version_snapshot.exists:
            committed_profile = {
                key: value
                for key, value in (version_snapshot.to_dict() or {}).items()
                if key != "snapshot_type"
            }
        else:
            committed_profile = {
                **profile,
                "source_document_ids": source_document_ids,
                "profile_version": current_version + 1,
                "created_at": current_profile.get("created_at", profile.get("created_at")),
                "profile_version_id": version_id,
            }
        version_payload = {
            **committed_profile,
            "snapshot_type": "canonical_profile_version",
        }

        if not version_snapshot.exists:
            transaction.set(version_ref, version_payload)
        transaction.set(profile_ref, committed_profile)
        transaction.set(
            current_cv_ref,
            {
                "profile_link_status": "active",
                "profile_version": committed_profile["profile_version"],
                "profile_version_id": version_id,
            },
            merge=True,
        )

        previous_cv_document_id = current_profile.get("active_cv_document_id")
        if previous_cv_document_id and previous_cv_document_id != cv_document_id:
            previous_cv_ref = client.collection(settings.cv_documents_collection).document(
                previous_cv_document_id
            )
            transaction.set(previous_cv_ref, {"profile_link_status": "superseded"}, merge=True)
        return committed_profile

    return commit_profile(client.transaction())


async def mark_profile_decision(cv_document_id: str, updates: dict) -> None:
    client = require_firestore()
    client.collection(settings.cv_documents_collection).document(cv_document_id).update(updates)
