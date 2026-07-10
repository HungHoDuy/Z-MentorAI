import logging
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "z-mentorai")
    use_firestore: bool = os.getenv("USE_FIRESTORE", "false").lower() == "true"
    firestore_database: str | None = os.getenv("FIRESTORE_DATABASE")
    cv_storage_bucket: str | None = os.getenv("CV_STORAGE_BUCKET")
    cv_documents_collection: str = os.getenv(
        "CV_DOCUMENTS_COLLECTION",
        "profile_scanner_cv_documents",
    )
    profiles_collection: str = os.getenv(
        "PROFILE_SCANNER_PROFILES_COLLECTION",
        "profile_scanner_profiles",
    )
    profile_versions_collection: str = os.getenv(
        "PROFILE_SCANNER_PROFILE_VERSIONS_COLLECTION",
        "profile_scanner_profile_versions",
    )
    alignment_results_collection: str = os.getenv(
        "PROFILE_SCANNER_ALIGNMENT_COLLECTION",
        "profile_scanner_alignment_results",
    )
    cv_max_file_size_bytes: int = int(os.getenv("CV_MAX_FILE_SIZE_BYTES", "10485760"))
    document_ai_location: str = os.getenv("DOCUMENT_AI_LOCATION", "us")
    document_ai_processor_id: str | None = os.getenv("DOCUMENT_AI_PROCESSOR_ID")
    document_ai_processor_name: str | None = os.getenv("DOCUMENT_AI_PROCESSOR_NAME")
    use_vertex_ai: bool = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
    vertex_ai_location: str = os.getenv("VERTEX_AI_LOCATION", "asia-southeast1")
    profile_ai_extraction_enabled: bool = os.getenv("PROFILE_AI_EXTRACTION_ENABLED", "false").lower() == "true"
    profile_ai_model_name: str = os.getenv("PROFILE_AI_MODEL_NAME", "gemini-2.5-flash")
    holland_collection_name: str = os.getenv(
        "HOLLAND_COLLECTION_NAME",
        "profile_scanner_holland_assessments",
    )
    assessments_collection_name: str = os.getenv(
        "ASSESSMENTS_COLLECTION_NAME",
        "profile_scanner_assessments",
    )
    holland_results_path: str = os.getenv(
        "HOLLAND_RESULTS_PATH",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "holland_results_db.json"),
    )
    assessments_results_path: str = os.getenv(
        "ASSESSMENTS_RESULTS_PATH",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "assessment_results_db.json"),
    )


settings = Settings()

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("profile_scanner")
