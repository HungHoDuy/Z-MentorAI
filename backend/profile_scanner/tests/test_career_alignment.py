import unittest

from career_alignment.service import (
    classify_alignment,
    compute_holland_alignment,
    resolve_profile_benchmark,
)


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

    def test_dynamic_benchmark_snapshot_resolves_without_static_uuid_lookup(self):
        benchmark = resolve_profile_benchmark({
            "benchmark_profile_id": "dynamic-uuid",
            "benchmark_snapshot": {
                "benchmark_id": "dynamic-uuid",
                "benchmark_type": "dynamic_market",
                "scoring_criteria": {"core_skills": ["python"]},
                "riasec": {"R": 0.2, "I": 1.0, "A": 0.3, "S": 0.2, "E": 0.2, "C": 0.5},
            },
        })
        self.assertEqual(benchmark["benchmark_id"], "dynamic-uuid")
        self.assertEqual(benchmark["core_skills"], ["python"])
        self.assertEqual(benchmark["riasec"]["I"], 1.0)

    def test_legacy_dynamic_profile_can_resolve_by_role_label(self):
        benchmark = resolve_profile_benchmark({
            "benchmark_profile_id": "legacy-uuid",
            "target_role": "AI Engineer",
        })
        self.assertEqual(benchmark["label"], "AI Engineer")


if __name__ == "__main__":
    unittest.main()
