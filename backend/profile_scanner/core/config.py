import logging
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    use_firestore: bool = os.getenv("USE_FIRESTORE", "false").lower() == "true"
    firestore_database: str | None = os.getenv("FIRESTORE_DATABASE")
    holland_collection_name: str = os.getenv(
        "HOLLAND_COLLECTION_NAME",
        "profile_scanner_holland_assessments",
    )
    holland_results_path: str = os.getenv(
        "HOLLAND_RESULTS_PATH",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "holland_results_db.json"),
    )


settings = Settings()

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger("profile_scanner")
