from skill_normalization.service import normalize_skills


def test_normalizes_aliases_and_removes_generic_duplicates():
    skills = normalize_skills(
        ["js", "JavaScript", "cloud", "GCP", "RESTful API", "made up skill"],
        "Built JavaScript services and RESTful API workloads on GCP.",
    )
    names = [item["canonical_name"] for item in skills]
    assert names == ["JavaScript", "Google Cloud Platform", "REST API"]
    assert skills[0]["skill_id"] == "javascript"


def test_rejects_skills_without_cv_evidence():
    skills = normalize_skills(["Python", "Kubernetes"], "Implemented services in Python.")
    assert [item["canonical_name"] for item in skills] == ["Python"]
