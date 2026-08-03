import unittest

from profile_ai_extraction.schemas import StructuredExperience, StructuredProfile
from profile_analysis.levels import infer_current_level, normalize_target_level


class TargetLevelTests(unittest.TestCase):
    def test_normalizes_supported_target_levels(self):
        self.assertEqual(normalize_target_level("AI Engineer Intern"), "intern")
        self.assertEqual(normalize_target_level("Fresher Data Analyst"), "fresher")
        self.assertEqual(normalize_target_level("Junior Backend Developer"), "junior")
        self.assertEqual(normalize_target_level("Middle AI Engineer"), "middle")
        self.assertEqual(normalize_target_level("Senior ML Engineer"), "senior")
        self.assertEqual(normalize_target_level("Tech Lead"), "lead")
        self.assertEqual(normalize_target_level("Engineering Manager"), "manager")

    def test_current_level_is_advisory_and_keeps_evidence(self):
        level, confidence, evidence = infer_current_level(StructuredProfile(
            work_experiences=[StructuredExperience(title="Senior AI Engineer")],
        ))
        self.assertEqual(level, "senior")
        self.assertGreaterEqual(confidence, 0.8)
        self.assertTrue(evidence)

    def test_unknown_target_level_stays_unresolved(self):
        self.assertIsNone(normalize_target_level("AI Engineer"))


if __name__ == "__main__":
    unittest.main()
