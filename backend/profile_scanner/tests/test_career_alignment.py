import unittest

from career_alignment.service import classify_alignment, compute_holland_alignment


class CareerAlignmentTests(unittest.TestCase):
    def test_identical_holland_distributions_are_fully_aligned(self):
        vector = {"R": 1, "I": 5, "A": 2, "S": 1, "E": 1, "C": 3}
        self.assertEqual(compute_holland_alignment(vector, vector), 100.0)

    def test_alignment_states_are_deterministic(self):
        self.assertEqual(classify_alignment(80, 80), ("aligned", "low"))
        self.assertEqual(classify_alignment(80, 40), ("interest_conflict", "high"))
        self.assertEqual(classify_alignment(40, 80), ("readiness_gap", "medium"))
        self.assertEqual(classify_alignment(40, 40), ("exploration_advised", "high"))
        self.assertEqual(classify_alignment(60, 60), ("mixed_or_uncertain", "medium"))


if __name__ == "__main__":
    unittest.main()
