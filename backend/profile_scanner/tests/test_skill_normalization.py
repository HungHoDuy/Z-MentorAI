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


def test_prioritizes_benchmark_skills_before_applying_limit():
    skills = normalize_skills(
        ["Docker", "Python", "SQL"],
        "Docker. Python Python Python. SQL SQL.",
        limit=2,
        priority_skills=["Docker"],
    )
    assert [item["canonical_name"] for item in skills] == ["Docker", "Python"]


def test_filters_non_skill_llm_phrases_and_formats_known_tools():
    skills = normalize_skills(
        ["Clear Technical Explanation", "Onsite Collaboration", "CI/CD", "T-SQL", "LangChain"],
        "Implemented CI/CD, T-SQL and LangChain in production.",
    )
    names = [item["canonical_name"] for item in skills]

    assert "Clear Technical Explanation" not in names
    assert "Onsite Collaboration" not in names
    assert {"CI/CD", "T-SQL", "LangChain"}.issubset(names)
