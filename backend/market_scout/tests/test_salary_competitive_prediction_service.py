from __future__ import annotations

from backend.market_scout.services.salary_benchmark.salary_competitive_prediction_service import (
    SalaryCompetitivePredictionService,
)


class FakeEmbeddingModel:
    def encode(self, texts: list[str], show_progress_bar: bool = False):
        assert texts
        return [[0.1] * 384]


class FakeSalaryModel:
    def predict(self, rows: list[list[float]]):
        assert len(rows) == 1
        assert len(rows[0]) == 467
        return [[13.2, 21.8]]


def test_predict_record_builds_expected_xgboost_feature_vector() -> None:
    location_field = "\u0110\u1ecba \u0111i\u1ec3m l\u00e0m vi\u1ec7c"
    level_field = "C\u1ea5p b\u1eadc"
    description_field = "M\u00f4 t\u1ea3 C\u00f4ng vi\u1ec7c"
    requirements_field = "Y\u00eau C\u1ea7u C\u00f4ng Vi\u1ec7c"
    industry_field = "Ng\u00e0nh ngh\u1ec1"
    features = (
        ["H\u00e0 N\u1ed9i", "H\u1ed3 Ch\u00ed Minh", "Other"]
        + ["level_Nh\u00e2n vi\u00ean", "level_Unknown"]
        + ["min_experience"]
        + [f"emb_{index}" for index in range(384)]
    )
    features += [f"extra_{index}" for index in range(467 - len(features))]
    service = SalaryCompetitivePredictionService(
        model=FakeSalaryModel(),
        features=features,
        embedding_model=FakeEmbeddingModel(),
    )

    result = service.predict_record(
        {
            "job_title": "Business Analyst",
            location_field: ["H\u00e0 N\u1ed9i"],
            level_field: "Nh\u00e2n vi\u00ean",
            "min_experience": 3,
            description_field: "Ph\u00e2n t\u00edch y\u00eau c\u1ea7u nghi\u1ec7p v\u1ee5.",
            requirements_field: "SQL, giao ti\u1ebfp t\u1ed1t.",
            industry_field: "CNTT",
        }
    )

    assert result.min_salary == 13.2
    assert result.max_salary == 21.8
    assert result.method == "competitive_xgboost"
