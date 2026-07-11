import json
import os
from typing import Optional

from core.config import logger, settings


firestore_client = None
FieldFilter = None

if settings.use_firestore:
    from google.cloud import firestore
    from google.cloud.firestore_v1.base_query import FieldFilter as FirestoreFieldFilter

    FieldFilter = FirestoreFieldFilter
    if settings.firestore_database and settings.firestore_database != "(default)":
        firestore_client = firestore.Client(database=settings.firestore_database)
    else:
        firestore_client = firestore.Client()


def read_local_results() -> dict:
    if not os.path.exists(settings.assessments_results_path):
        return {"assessments": {}}
    try:
        with open(settings.assessments_results_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {"assessments": {}}


def write_local_results(data: dict) -> None:
    with open(settings.assessments_results_path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


async def save_assessment_result(result: dict) -> None:
    if settings.use_firestore:
        logger.info(
            "Saving assessment result",
            extra={
                "assessment_id": result.get("assessment_id"),
                "assessment_type": result.get("assessment_type"),
                "user_id": result.get("user_id"),
                "collection": settings.assessments_collection_name,
            },
        )
        firestore_client.collection(settings.assessments_collection_name).document(result["assessment_id"]).set(result)
        return

    data = read_local_results()
    data["assessments"][result["assessment_id"]] = result
    write_local_results(data)


async def get_latest_assessment_result(user_id: str, assessment_type: str) -> Optional[dict]:
    if settings.use_firestore:
        docs = (
            firestore_client.collection(settings.assessments_collection_name)
            .where(filter=FieldFilter("user_id", "==", user_id))
            .where(filter=FieldFilter("assessment_type", "==", assessment_type))
            .order_by("created_at", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        for doc in docs:
            return doc.to_dict()
        return None

    data = read_local_results()
    assessments = [
        item for item in data.get("assessments", {}).values()
        if item.get("user_id") == user_id and item.get("assessment_type") == assessment_type
    ]
    assessments.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return assessments[0] if assessments else None
