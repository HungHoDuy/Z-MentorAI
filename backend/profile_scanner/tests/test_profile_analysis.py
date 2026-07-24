import unittest

from profile_analysis.service import (
    analysis_benchmark_is_fresh,
    career_readiness_text_from_ai,
    compute_total_score,
    detect_target_role,
    extract_education_lines,
    extract_matching_skills,
    extract_project_lines,
    extract_work_experience_lines,
    grade_from_score,
    infer_candidate_benchmark_level,
    profile_lines_from_ai,
    score_career_readiness,
    score_cv_clarity,
    score_education_certification,
    score_experience_evidence,
    score_role_skill_fit,
    resolve_target_role,
)
from profile_ai_extraction.schemas import StructuredEducation, StructuredExperience, StructuredProfile
from profile_analysis.benchmark import ROLE_BENCHMARKS, SKILL_ALIASES


SAMPLE_DATA_ANALYST_CV = """
Nguyen Van A
Email: analyst@example.com
LinkedIn: linkedin.com/in/analyst
GitHub: github.com/analyst

Education: Bachelor of Computer Science
Skills: Python, SQL, Excel, Power BI, Tableau, statistics, dashboard, Git
Experience: Data Analyst Intern 2024. Built SQL dashboards and improved reporting time
by 30% for 200 users.
Project: Sales dashboard using Python, SQL and Power BI. Presented insights to the team.
"""


class ProfileAnalysisTests(unittest.TestCase):
    def test_dynamic_benchmark_reuse_requires_unexpired_snapshot(self):
        self.assertTrue(
            analysis_benchmark_is_fresh(
                {
                    "benchmark_type": "dynamic_market",
                    "benchmark_snapshot": {"expires_at": "2099-01-01T00:00:00+00:00"},
                }
            )
        )
        self.assertFalse(
            analysis_benchmark_is_fresh(
                {
                    "benchmark_type": "dynamic_market",
                    "benchmark_snapshot": {"expires_at": "2000-01-01T00:00:00+00:00"},
                }
            )
        )
        self.assertFalse(
            analysis_benchmark_is_fresh(
                {"benchmark_type": "dynamic_market", "benchmark_snapshot": {}}
            )
        )

    def test_structured_profile_supplies_multilingual_section_evidence(self):
        profile = StructuredProfile(
            skills=["Python", "PyTorch", "FastAPI", "GCP", "LLM"],
            work_experiences=[
                StructuredExperience(
                    title="AI project",
                    summary="Developed and deployed an AI service.",
                )
            ],
            education=[
                StructuredEducation(
                    institution="FPT University",
                    field="Artificial Intelligence",
                )
            ],
        )

        dimension = score_cv_clarity(
            "経歴書\n" + ("職務内容\n" * 25),
            profile.skills,
            profile,
        )

        self.assertIn("experience", dimension.evidence)
        self.assertIn("education", dimension.evidence)
        self.assertIn("skills", dimension.evidence)

    def test_readiness_recognizes_validation_security_and_certification(self):
        profile = StructuredProfile(
            career_readiness_signals=["root-cause investigation", "security validation"],
            certifications=["Deep Learning - DeepLearning.AI"],
        )
        dimension = score_career_readiness(
            career_readiness_text_from_ai(profile)
        )

        self.assertIn("critical thinking", dimension.evidence)
        self.assertIn("professionalism", dimension.evidence)
        self.assertIn("career self-development", dimension.evidence)

    def test_structured_work_skills_are_available_to_evidence_scoring(self):
        profile = StructuredProfile(
            work_experiences=[
                StructuredExperience(
                    title="AI Engineer",
                    summary="Developed an object detection service.",
                    skills=["Python", "PyTorch", "Computer Vision"],
                )
            ]
        )
        work_lines, _, _, _ = profile_lines_from_ai(profile)
        benchmark = {
            "core_skills": ["python", "pytorch"],
            "essential_skill_groups": [["python"], ["pytorch"]],
            "supporting_skills": [],
            "skill_aliases": {
                "python": ["python"],
                "pytorch": ["pytorch"],
            },
            "skill_weights": {
                "python": 0.6,
                "pytorch": 0.4,
            },
        }

        dimension = score_role_skill_fit(
            ["Python", "PyTorch"],
            benchmark,
            text="\n".join(work_lines),
            work_lines=work_lines,
        )

        self.assertEqual(dimension.score, 80)

    def test_grade_thresholds(self):
        self.assertEqual(grade_from_score(90), "S")
        self.assertEqual(grade_from_score(80), "A")
        self.assertEqual(grade_from_score(70), "B")
        self.assertEqual(grade_from_score(60), "C")
        self.assertEqual(grade_from_score(50), "D")
        self.assertEqual(grade_from_score(49.99), "E")

    def test_short_alias_does_not_match_inside_word(self):
        skills = extract_matching_skills("Presented insights to stakeholders.")
        self.assertNotIn("typescript", skills)

    def test_data_analyst_profile_scores_consistently(self):
        skills = extract_matching_skills(SAMPLE_DATA_ANALYST_CV)
        slug, benchmark = detect_target_role(
            SAMPLE_DATA_ANALYST_CV,
            message="Scan this CV for a Junior Data Analyst role.",
        )
        work = extract_work_experience_lines(SAMPLE_DATA_ANALYST_CV)
        projects = extract_project_lines(SAMPLE_DATA_ANALYST_CV)
        education = extract_education_lines(SAMPLE_DATA_ANALYST_CV)
        dimensions = [
            score_role_skill_fit(skills, benchmark, SAMPLE_DATA_ANALYST_CV, work, projects),
            score_experience_evidence(SAMPLE_DATA_ANALYST_CV, work, projects),
            score_education_certification(SAMPLE_DATA_ANALYST_CV, education, benchmark),
            score_career_readiness(SAMPLE_DATA_ANALYST_CV),
            score_cv_clarity(SAMPLE_DATA_ANALYST_CV, skills),
        ]

        self.assertEqual(slug, "data_analyst")
        self.assertIn("sql", skills)
        self.assertGreaterEqual(compute_total_score(dimensions), 65)

    def test_ai_engineer_is_not_forced_to_backend(self):
        resolution = resolve_target_role(
            "AI Engineer with Python, PyTorch, TensorFlow, LLM, RAG, Docker and GCP.",
            target_role="Junior AI Engineer",
        )
        self.assertEqual(resolution.slug, "ai_engineer")
        self.assertEqual(resolution.source, "user_target")
        self.assertGreaterEqual(resolution.confidence, 0.95)

    def test_backend_keyword_in_experience_does_not_override_cv_header(self):
        cv_text = """
Candidate Name
candidate@example.com
Profile
Aspiring AI specialist focused on machine learning and natural language processing.
Education
Bachelor of Artificial Intelligence
Experience
Built Firebase hosting and backend services for a learning platform.
"""
        resolution = resolve_target_role(cv_text)

        self.assertIsNone(resolution.slug)
        self.assertEqual(resolution.source, "unresolved")

    def test_normalized_skill_names_match_static_benchmark_aliases(self):
        text = """
AI Engineer
Built Python machine learning and LLM applications with NLP, SQL, APIs and GCP.
Deployed a model service to Google Cloud Platform using Docker.
"""
        dimension = score_role_skill_fit(
            [
                "Python",
                "Machine Learning",
                "LLM",
                "NLP",
                "SQL",
                "Google Cloud Platform",
                "Docker",
            ],
            ROLE_BENCHMARKS["ai_engineer"],
            text=text,
            work_lines=[text],
        )

        self.assertGreater(dimension.score, 50)
        self.assertTrue(dimension.evidence)

    def test_gcp_benchmark_id_matches_google_cloud_platform_canonical_name(self):
        benchmark = {
            "core_skills": ["gcp"],
            "essential_skill_groups": [["gcp"]],
            "supporting_skills": [],
            "skill_aliases": {"gcp": SKILL_ALIASES["gcp"]},
        }
        dimension = score_role_skill_fit(
            ["Google Cloud Platform"],
            benchmark,
            text="Deployed an API to Google Cloud Platform and Cloud Run.",
            project_lines=["Deployed an API to Google Cloud Platform and Cloud Run."],
        )

        self.assertGreater(dimension.score, 0)
        self.assertEqual(dimension.missing, [])

    def test_experience_without_impact_does_not_saturate_score(self):
        dimension = score_experience_evidence(
            "Built and developed internal applications.",
            work_lines=["Software Engineer 2024", "Built an internal service."],
            project_lines=["Internal application", "API project"],
        )

        self.assertLess(dimension.score, 100)
        self.assertIn("No quantified achievement or measurable impact detected", dimension.missing)

    def test_accountant_is_not_forced_to_data_analyst(self):
        resolution = resolve_target_role(
            "Accountant responsible for audit, tax, financial reporting and Excel.",
            target_role="Accountant",
        )
        self.assertEqual(resolution.slug, "accountant")

    def test_unsupported_role_is_not_scored_as_nearest_technical_role(self):
        resolution = resolve_target_role(
            "Python SQL Docker API",
            target_role="Marine Biologist",
        )
        self.assertIsNone(resolution.slug)
        self.assertEqual(resolution.source, "unresolved")

    def test_candidate_level_prefers_explicit_target_and_uses_profile_as_fallback(self):
        senior_profile = StructuredProfile(
            work_experiences=[StructuredExperience(title="Senior AI Engineer")],
        )
        student_profile = StructuredProfile(
            headline="Final-year student",
            work_experiences=[StructuredExperience(title="AI Intern")],
        )

        self.assertEqual(
            infer_candidate_benchmark_level("Junior AI Engineer", senior_profile, ""),
            "entry",
        )
        self.assertEqual(
            infer_candidate_benchmark_level("AI Engineer", senior_profile, ""),
            "senior",
        )
        self.assertEqual(
            infer_candidate_benchmark_level("AI Engineer", student_profile, ""),
            "entry",
        )

    def test_generic_project_leader_does_not_force_senior_market_cohort(self):
        profile = StructuredProfile(
            headline="Second-year AI student",
            work_experiences=[StructuredExperience(title="Project Leader")],
        )

        self.assertEqual(
            infer_candidate_benchmark_level("AI Engineer", profile, ""),
            "entry",
        )

    def test_education_student_signal_selects_entry_market_cohort(self):
        profile = StructuredProfile(
            headline="Aspiring AI Engineer",
            education=[
                StructuredEducation(
                    degree="Bachelor candidate",
                    field="Artificial Intelligence",
                    evidence="Second-year student",
                )
            ],
        )

        self.assertEqual(
            infer_candidate_benchmark_level("AI Engineer", profile, ""),
            "entry",
        )


if __name__ == "__main__":
    unittest.main()
