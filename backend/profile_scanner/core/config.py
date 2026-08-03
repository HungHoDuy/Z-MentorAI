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
    cv_extractions_collection: str = os.getenv(
        "PROFILE_SCANNER_CV_EXTRACTIONS_COLLECTION",
        "profile_scanner_cv_extractions",
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
    dynamic_benchmark_enabled: bool = os.getenv("DYNAMIC_BENCHMARK_ENABLED", "false").lower() == "true"
    benchmark_snapshots_collection: str = os.getenv(
        "BENCHMARK_SNAPSHOTS_COLLECTION",
        "profile_scanner_benchmark_snapshots",
    )
    benchmark_cache_collection: str = os.getenv(
        "BENCHMARK_CACHE_COLLECTION",
        "profile_scanner_benchmark_cache",
    )
    benchmark_job_facts_collection: str = os.getenv(
        "BENCHMARK_JOB_FACTS_COLLECTION",
        "trend_job_facts_v2",
    )
    benchmark_embedding_collection: str = os.getenv(
        "BENCHMARK_EMBEDDING_COLLECTION",
        "job_mapping_embedding",
    )
    benchmark_embedding_field: str = os.getenv("BENCHMARK_EMBEDDING_FIELD", "embedding")
    benchmark_embedding_model: str = os.getenv(
        "BENCHMARK_EMBEDDING_MODEL",
        "text-multilingual-embedding-002",
    )
    benchmark_embedding_location: str = os.getenv("BENCHMARK_EMBEDDING_LOCATION", "us-central1")
    benchmark_embedding_dimension: int = int(os.getenv("BENCHMARK_EMBEDDING_DIMENSION", "768"))
    benchmark_market_window_days: int = int(os.getenv("BENCHMARK_MARKET_WINDOW_DAYS", "365"))
    benchmark_cache_days: int = int(os.getenv("BENCHMARK_CACHE_DAYS", "7"))
    benchmark_search_limit: int = int(os.getenv("BENCHMARK_SEARCH_LIMIT", "200"))
    benchmark_max_vector_distance: float = float(os.getenv("BENCHMARK_MAX_VECTOR_DISTANCE", "0.38"))
    benchmark_min_skill_share: float = float(os.getenv("BENCHMARK_MIN_SKILL_SHARE", "0.05"))
    benchmark_essential_skill_share: float = float(os.getenv("BENCHMARK_ESSENTIAL_SKILL_SHARE", "0.30"))
    benchmark_max_skills: int = int(os.getenv("BENCHMARK_MAX_SKILLS", "24"))
    benchmark_default_location: str = os.getenv("BENCHMARK_DEFAULT_LOCATION", "vietnam")
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
