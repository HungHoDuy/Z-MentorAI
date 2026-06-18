import unittest

from profile_analysis.service import (
    compute_total_score,
    detect_target_role,
    extract_education_lines,
    extract_matching_skills,
    extract_project_lines,
    extract_work_experience_lines,
    grade_from_score,
    score_career_readiness,
    score_cv_clarity,
    score_education_certification,
    score_experience_evidence,
    score_role_skill_fit,
)


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
            score_role_skill_fit(skills, benchmark),
            score_experience_evidence(SAMPLE_DATA_ANALYST_CV, work, projects),
            score_education_certification(SAMPLE_DATA_ANALYST_CV, education, benchmark),
            score_career_readiness(SAMPLE_DATA_ANALYST_CV),
            score_cv_clarity(SAMPLE_DATA_ANALYST_CV, skills),
        ]

        self.assertEqual(slug, "data_analyst")
        self.assertIn("sql", skills)
        self.assertGreaterEqual(compute_total_score(dimensions), 80)


if __name__ == "__main__":
    unittest.main()
