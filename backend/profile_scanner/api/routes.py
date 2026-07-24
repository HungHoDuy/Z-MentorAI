from fastapi import APIRouter
from fastapi.responses import JSONResponse
from google.api_core.client_options import ClientOptions
from google.cloud import documentai
from google.cloud import storage

from core.config import settings
from cv_extraction.service import get_document_ai_processor_name
from cv_intake.repository import firestore_client


router = APIRouter(tags=["system"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "service": "profile_scanner"}


@router.get("/ready")
async def readiness_check():
    checks = {
        "firestore": {"status": "unknown"},
        "gcs": {"status": "unknown"},
        "document_ai": {
            "status": "configured"
            if settings.document_ai_processor_name or settings.document_ai_processor_id
            else "missing",
        },
        "profile_ai": {
            "status": "configured"
            if settings.profile_ai_extraction_enabled
            and (settings.use_vertex_ai or bool(settings.google_api_key))
            else "disabled_or_missing",
        },
    }
    try:
        if firestore_client is None:
            raise RuntimeError("Firestore client is not configured.")
        list(
            firestore_client.collection(settings.cv_documents_collection)
            .limit(1)
            .stream()
        )
        checks["firestore"] = {"status": "ok"}
    except Exception as exc:
        checks["firestore"] = {"status": "error", "error_type": type(exc).__name__}

    try:
        if not settings.cv_storage_bucket:
            raise RuntimeError("CV storage bucket is not configured.")
        bucket = storage.Client().bucket(settings.cv_storage_bucket)
        if not bucket.exists():
            raise RuntimeError("Configured CV storage bucket does not exist or is inaccessible.")
        checks["gcs"] = {"status": "ok", "bucket": settings.cv_storage_bucket}
    except Exception as exc:
        checks["gcs"] = {"status": "error", "error_type": type(exc).__name__}

    try:
        processor_name = get_document_ai_processor_name()
        if not processor_name:
            raise RuntimeError("Document AI processor is not configured.")
        client = documentai.DocumentProcessorServiceClient(
            client_options=ClientOptions(
                api_endpoint=f"{settings.document_ai_location}-documentai.googleapis.com",
            )
        )
        processor = client.get_processor(name=processor_name)
        checks["document_ai"] = {
            "status": "ok",
            "processor": processor.name,
        }
    except Exception as exc:
        checks["document_ai"] = {"status": "error", "error_type": type(exc).__name__}

    ready = (
        checks["firestore"]["status"] == "ok"
        and checks["gcs"]["status"] == "ok"
        and checks["document_ai"]["status"] == "ok"
    )
    payload = {
        "status": "ready" if ready else "degraded",
        "service": "profile_scanner",
        "checks": checks,
    }
    return JSONResponse(status_code=200 if ready else 503, content=payload)
