from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "market_scout_crawling" / "downloaded_model_artifacts"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSION = 384

COMPANY_FIELD = "C\u00f4ng ty"
INDUSTRY_FIELD = "Ng\u00e0nh ngh\u1ec1"
LEVEL_FIELD = "C\u1ea5p b\u1eadc"
DESCRIPTION_FIELD = "M\u00f4 t\u1ea3 C\u00f4ng vi\u1ec7c"
REQUIREMENTS_FIELD = "Y\u00eau C\u1ea7u C\u00f4ng Vi\u1ec7c"
LOCATION_FIELD = "\u0110\u1ecba \u0111i\u1ec3m l\u00e0m vi\u1ec7c"


@dataclass(frozen=True)
class SalaryPredictionResult:
    min_salary: float
    max_salary: float
    method: str = "competitive_xgboost"


class SalaryCompetitivePredictionService:
    """Predict salary bounds for CareerViet jobs with competitive/hidden salary text."""

    def __init__(
        self,
        *,
        artifact_dir: str | Path | None = None,
        embedding_model_name: str = DEFAULT_EMBEDDING_MODEL,
        model: Any | None = None,
        features: list[str] | None = None,
        embedding_model: Any | None = None,
    ) -> None:
        self.artifact_dir = Path(artifact_dir) if artifact_dir else DEFAULT_ARTIFACT_DIR
        self.embedding_model_name = embedding_model_name
        self._model: Any | None = model
        self._features: list[str] | None = [str(feature) for feature in features] if features is not None else None
        self._embedding_model: Any | None = embedding_model

    def predict_record(self, record: dict[str, Any]) -> SalaryPredictionResult:
        features = self._load_features()
        model = self._load_model()
        embedding = self._embed_record(record)
        feature_values = self._build_feature_values(record, embedding)
        row = [[feature_values.get(feature_name, 0.0) for feature_name in features]]
        prediction = model.predict(row)[0]
        min_salary = float(prediction[0])
        max_salary = float(prediction[1])
        if min_salary <= 0 or max_salary <= 0:
            raise ValueError(f"XGBoost predicted non-positive salary bounds: {prediction!r}")
        if min_salary > max_salary:
            min_salary, max_salary = max_salary, min_salary
        return SalaryPredictionResult(min_salary=round(min_salary, 2), max_salary=round(max_salary, 2))

    def _build_feature_values(self, record: dict[str, Any], embedding: list[float]) -> dict[str, float]:
        features = self._load_features()
        values: dict[str, float] = {feature: 0.0 for feature in features}

        location_features = [feature for feature in features if not feature.startswith("level_") and feature != "min_experience" and not feature.startswith("emb_")]
        matched_location = False
        record_locations = record.get(LOCATION_FIELD) or []
        if not isinstance(record_locations, list):
            record_locations = [record_locations]
        normalized_locations = {_normalize_text(location) for location in record_locations if location}
        for feature in location_features:
            if feature != "Other" and _normalize_text(feature) in normalized_locations:
                values[feature] = 1.0
                matched_location = True
        if not matched_location and "Other" in values:
            values["Other"] = 1.0

        level = _normalize_text(record.get(LEVEL_FIELD)) or "unknown"
        matched_level = False
        for feature in [feature for feature in features if feature.startswith("level_")]:
            label = feature.removeprefix("level_")
            if _normalize_text(label) == level:
                values[feature] = 1.0
                matched_level = True
        if not matched_level and "level_Unknown" in values:
            values["level_Unknown"] = 1.0

        min_experience = record.get("min_experience")
        values["min_experience"] = _safe_float(min_experience) or 0.0

        if len(embedding) != EMBEDDING_DIMENSION:
            raise ValueError(f"Expected {EMBEDDING_DIMENSION} embedding dimensions, got {len(embedding)}")
        for index, value in enumerate(embedding):
            values[f"emb_{index}"] = float(value)

        return values

    def _embed_record(self, record: dict[str, Any]) -> list[float]:
        text = self._build_embedding_text(record)
        model = self._load_embedding_model()
        embedding = model.encode([text], show_progress_bar=False)[0]
        return [float(value) for value in embedding]

    def _build_embedding_text(self, record: dict[str, Any]) -> str:
        return "\n".join(
            [
                f"[Ch\u1ee9c danh]: {_clean_text(record.get('job_title') or record.get('title'))}",
                f"[M\u00f4 t\u1ea3 C\u00f4ng vi\u1ec7c]: {_clean_text(record.get(DESCRIPTION_FIELD))}",
                f"[Y\u00eau C\u1ea7u C\u00f4ng Vi\u1ec7c]: {_clean_text(record.get(REQUIREMENTS_FIELD))}",
                f"[Ng\u00e0nh ngh\u1ec1]: {_clean_text(record.get(INDUSTRY_FIELD))}",
            ]
        )

    def _load_model(self) -> Any:
        if self._model is None:
            import joblib

            model_path = self.artifact_dir / "salary_prediction_xgb.pkl"
            if not model_path.exists():
                raise FileNotFoundError(f"Missing salary prediction model: {model_path}")
            self._model = joblib.load(model_path)
        return self._model

    def _load_features(self) -> list[str]:
        if self._features is None:
            import joblib

            features_path = self.artifact_dir / "model_features.joblib"
            if not features_path.exists():
                raise FileNotFoundError(f"Missing salary model features: {features_path}")
            features = joblib.load(features_path)
            if not isinstance(features, list) or len(features) == 0:
                raise ValueError("Salary model features artifact must be a non-empty list.")
            self._features = [str(feature) for feature in features]
        return self._features

    def _load_embedding_model(self) -> Any:
        if self._embedding_model is None:
            from sentence_transformers import SentenceTransformer

            self._embedding_model = SentenceTransformer(self.embedding_model_name)
        return self._embedding_model


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value if item not in (None, ""))
    elif isinstance(value, dict):
        value = " ".join(str(item) for item in value.values() if item not in (None, ""))
    return " ".join(str(value).split())


def _normalize_text(value: Any) -> str:
    import unicodedata

    text = _clean_text(value).replace("\u0111", "d").replace("\u0110", "D")
    text = unicodedata.normalize("NFD", text)
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    return " ".join(text.casefold().split())


def _safe_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number):
        return None
    return number
