import unittest
from unittest.mock import AsyncMock, patch

from career_alignment.service import (
    classify_alignment,
    compute_holland_alignment,
    resolve_profile_benchmark,
    synthesize_career_alignment,
)
from guidance.schemas import CareerAlignmentNarrative


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


class CareerAlignmentIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_synthesis_keeps_rule_decision_and_adds_personalized_narrative(self):
        profile = {
            "user_id": "user-1",
            "target_role": "AI Engineer",
            "target_level": "junior",
            "total_score": 76,
            "benchmark_profile_id": "ai_engineer",
            "benchmark_snapshot": {
                "benchmark_id": "ai_engineer",
                "riasec": {"R": 0.2, "I": 1.0, "A": 0.4, "S": 0.2, "E": 0.2, "C": 0.5},
            },
            "extracted_skills": ["Python", "Machine Learning"],
        }
        holland = {
            "top_code": "I-A-C",
            "scores": {"R": 0.2, "I": 1.0, "A": 0.4, "S": 0.2, "E": 0.2, "C": 0.5},
        }
        narrative = CareerAlignmentNarrative(
            executive_summary_vi="CV và sở thích nghề nghiệp hiện cho tín hiệu đồng nhất với vai trò mục tiêu đã chọn.",
            strengths_vi=["Kỹ năng Python và Machine Learning xuất hiện trong hồ sơ."],
            watchouts_vi=[],
            action_plan_vi=[
                "Bổ sung một dự án có metric đánh giá rõ ràng.",
                "Chuẩn bị phần giải thích quyết định mô hình cho phỏng vấn.",
            ],
            learning_strategy_vi="Học qua bài toán có dữ liệu và sơ đồ luồng xử lý.",
        )
        with (
            patch("career_alignment.service.get_canonical_profile", new=AsyncMock(return_value=profile)),
            patch("career_alignment.service.get_latest_holland_assessment", new=AsyncMock(return_value=holland)),
            patch("career_alignment.service.get_latest_assessment_result", new=AsyncMock(return_value={"top_dimensions": ["logical_math"]})),
            patch("career_alignment.service.generate_alignment_narrative", new=AsyncMock(return_value=(narrative, "vertex_ai"))),
            patch("career_alignment.service.save_alignment_result", new=AsyncMock()) as save_result,
        ):
            result = await synthesize_career_alignment("user-1")

        self.assertEqual(result.alignment_state, "aligned")
        self.assertEqual(result.guidance_source, "vertex_ai")
        self.assertEqual(result.executive_summary_vi, narrative.executive_summary_vi)
        self.assertEqual(result.action_plan_vi, narrative.action_plan_vi)
        save_result.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
