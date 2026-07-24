import datetime

from dynamic_benchmark.compiler import (
    build_skill_criteria,
    canonical_skill_id,
    compile_dynamic_benchmark,
    infer_level,
    sanitize_skill_vocabulary,
)
from dynamic_benchmark.schemas import MarketJobEvidence
from profile_analysis.service import extract_matching_skills, score_role_skill_fit


def make_jobs(count: int) -> list[MarketJobEvidence]:
    return [
        MarketJobEvidence(
            job_key=f"job-{index}",
            job_title="Junior AI Engineer",
            company=f"company-{index % 7}",
            job_url=f"https://example.com/jobs/{index}",
            source=f"test-source-{index % 2}",
            source_updated_at="2026-06-01",
            seniority="nhan-vien",
            location_ids=["ho-chi-minh"],
            requirements_text="Python SQL Docker Git and machine learning are required.",
            description_text="Build machine learning APIs with Python and Docker.",
            match_score=0.8,
        )
        for index in range(count)
    ]


def vocabulary(_role: str, _jobs: list[MarketJobEvidence]) -> dict:
    return {
        "normalized_role": "AI Engineer",
        "source": "ai_proposed_deterministically_counted",
        "education_keywords": ["computer science", "machine learning"],
        "skills": [
            {"name": "python", "aliases": ["python"]},
            {"name": "sql", "aliases": ["sql"]},
            {"name": "docker", "aliases": ["docker"]},
            {"name": "git", "aliases": ["git"]},
            {"name": "machine learning", "aliases": ["machine learning", "ml"]},
        ],
    }


class FakeRepository:
    def __init__(self, jobs: list[MarketJobEvidence], cached=None):
        self.jobs = jobs
        self.cached = cached
        self.saved = None
        self.search_args = None

    def get_cached(self, _cache_key, _now):
        return self.cached

    def search_market_jobs(self, **kwargs):
        self.search_args = kwargs
        return self.jobs

    def save(self, snapshot):
        self.saved = snapshot


def test_infer_level_from_role_title():
    assert infer_level("Junior AI Engineer") == "entry"
    assert infer_level("Senior Data Engineer") == "senior"
    assert infer_level("Product Manager") == "manager"
    assert infer_level("Data Analyst") == "unspecified"
    assert infer_level("Leadership Coach") == "unspecified"
    assert infer_level("Headless CMS Developer") == "unspecified"
    assert infer_level("Graduate Admissions Manager") == "manager"


def test_noisy_ai_vocabulary_is_canonicalized_and_merged():
    skills = sanitize_skill_vocabulary([
        {"name": "Artificial Intelligence / AI", "aliases": ["AI"]},
        {"name": "artificial intelligence", "aliases": ["artificial intelligence"]},
        {"name": "PyTorch", "aliases": ["torch"]},
    ])

    by_name = {item["name"]: item for item in skills}
    assert "artificial intelligence" in by_name
    assert "pytorch" in by_name
    assert len([item for item in skills if item["name"] == "artificial intelligence"]) == 1
    assert canonical_skill_id("Machine Learning / ML") == "machine learning"


def test_compile_high_confidence_market_benchmark_with_365_day_window():
    repository = FakeRepository(make_jobs(35))
    now = datetime.datetime(2026, 7, 11, tzinfo=datetime.timezone.utc)

    snapshot = compile_dynamic_benchmark(
        role_query="Junior AI Engineer",
        location_id="vietnam",
        repository=repository,
        vocabulary_extractor=vocabulary,
        now=now,
    )

    assert snapshot.status == "ready"
    assert snapshot.confidence == "high"
    assert snapshot.window_days == 365
    assert snapshot.cohort_size == 35
    assert snapshot.distinct_company_count == 7
    assert snapshot.vocabulary_source == "ai_proposed_deterministically_counted"
    assert len(snapshot.skill_criteria) == 5
    assert repository.saved == snapshot
    assert repository.search_args["window_days"] == 365


def test_compile_refuses_to_grade_small_role_cohort():
    snapshot = compile_dynamic_benchmark(
        role_query="Marine Biologist",
        repository=FakeRepository(make_jobs(5)),
        vocabulary_extractor=vocabulary,
        now=datetime.datetime(2026, 7, 11, tzinfo=datetime.timezone.utc),
    )

    assert snapshot.status == "insufficient_evidence"
    assert snapshot.confidence == "low"


def test_single_market_source_caps_confidence_at_medium():
    jobs = [job.model_copy(update={"source": "careerviet"}) for job in make_jobs(35)]
    snapshot = compile_dynamic_benchmark(
        role_query="Junior AI Engineer",
        repository=FakeRepository(jobs),
        vocabulary_extractor=vocabulary,
        now=datetime.datetime(2026, 7, 11, tzinfo=datetime.timezone.utc),
    )

    assert snapshot.status == "ready"
    assert snapshot.confidence == "medium"
    assert any("one independent" in item for item in snapshot.limitations)


def test_market_weights_drive_role_skill_score_deterministically():
    criteria = build_skill_criteria(make_jobs(20), vocabulary("AI Engineer", [])["skills"])
    aliases = {criterion.skill_id: criterion.aliases for criterion in criteria}
    skills = extract_matching_skills("Python Docker machine learning project", aliases)
    benchmark = {
        "core_skills": [criterion.skill_id for criterion in criteria if criterion.tier == "essential"],
        "essential_skill_groups": [[criterion.skill_id] for criterion in criteria if criterion.tier == "essential"],
        "supporting_skills": [criterion.skill_id for criterion in criteria if criterion.tier != "essential"],
        "skill_aliases": aliases,
        "skill_weights": {criterion.skill_id: criterion.weight for criterion in criteria},
    }

    dimension = score_role_skill_fit(
        skills,
        benchmark,
        text="Built a Python Docker machine learning project.",
        project_lines=["Built a Python Docker machine learning project."],
    )

    assert 0 < dimension.score < 100
    assert "python" in skills
    assert "sql" in dimension.missing


def test_dynamic_score_is_not_capped_when_benchmark_has_no_supporting_skills():
    text = "Built and deployed Python services; reduced inference latency by 40%."
    dimension = score_role_skill_fit(
        ["Python"],
        {
            "core_skills": ["python"],
            "essential_skill_groups": [["python"]],
            "supporting_skills": [],
            "skill_aliases": {"python": ["python"]},
            "skill_weights": {"python": 1.0},
        },
        text=text,
        project_lines=[text],
    )

    assert dimension.score == 100


def test_explicit_skill_owns_its_alias_in_market_frequency_counting():
    jobs = [
        job.model_copy(
            update={
                "requirements_text": "PyTorch production experience required.",
                "description_text": "Build models using PyTorch.",
            }
        )
        for job in make_jobs(10)
    ]
    criteria = build_skill_criteria(
        jobs,
        [
            {"name": "machine learning", "aliases": ["machine learning", "pytorch"]},
            {"name": "pytorch", "aliases": ["pytorch", "torch"]},
        ],
    )

    assert [criterion.skill_id for criterion in criteria] == ["pytorch"]


def test_dynamic_score_rewards_a_strong_specialization_without_requiring_every_track():
    benchmark = {
        "core_skills": ["artificial intelligence", "python"],
        "essential_skill_groups": [["artificial intelligence"], ["python"]],
        "supporting_skills": ["computer vision", "llm", "rag", "nlp", "data engineering"],
        "skill_aliases": {
            "artificial intelligence": ["artificial intelligence", "ai"],
            "python": ["python"],
            "computer vision": ["computer vision"],
            "llm": ["llm"],
            "rag": ["rag"],
            "nlp": ["nlp"],
            "data engineering": ["data engineering"],
        },
        "skill_weights": {
            "artificial intelligence": 0.25,
            "python": 0.20,
            "computer vision": 0.14,
            "llm": 0.12,
            "rag": 0.11,
            "nlp": 0.10,
            "data engineering": 0.08,
        },
        "supporting_target_count": 3,
    }
    text = "Built and deployed Python AI applications using LLM, RAG and NLP."
    dimension = score_role_skill_fit(
        ["Artificial Intelligence", "Python", "LLM", "RAG", "NLP"],
        benchmark,
        text=text,
        work_lines=[text],
    )

    assert dimension.score >= 70
    assert "computer vision" not in dimension.missing
