import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from guidance.service import generate_alignment_narrative, generate_mi_guidance


class FakeLlm:
    def __init__(self, payload):
        self.payload = payload

    async def ainvoke(self, _messages):
        return SimpleNamespace(content=json.dumps(self.payload, ensure_ascii=False))


class GuidanceTests(unittest.IsolatedAsyncioTestCase):
    async def test_mi_guidance_uses_validated_ai_output(self):
        payload = {
            "learning_profile_summary_vi": "Bạn tiếp nhận tốt nội dung có cấu trúc logic và hình ảnh trực quan, nhưng vẫn cần kiểm chứng bằng sản phẩm thực tế.",
            "learning_strategies_vi": [
                "Vẽ sơ đồ luồng trước khi triển khai một chức năng.",
                "Đặt metric rõ ràng cho mỗi bài thực hành.",
            ],
            "application_examples_vi": [
                "Mô tả kiến trúc dự án bằng sơ đồ và đối chiếu với kết quả chạy.",
            ],
        }
        with patch("guidance.service.get_guidance_llm", return_value=FakeLlm(payload)):
            guidance, source = await generate_mi_guidance(
                result={
                    "user_id": "user-1",
                    "scores": {"logical_math": 0.8, "spatial": 0.7},
                    "top_dimensions": ["logical_math", "spatial"],
                    "score_margin": 0.1,
                },
                dimension_labels={"logical_math": "Logic / Toán học", "spatial": "Không gian / Hình ảnh"},
                fallback_recommendations=["Fallback one", "Fallback two"],
                profile={"target_role": "AI Engineer", "extracted_skills": ["Python"]},
            )

        self.assertEqual(source, "vertex_ai")
        self.assertEqual(guidance.learning_strategies_vi, payload["learning_strategies_vi"])

    async def test_invalid_mi_output_falls_back_without_failing_score(self):
        with (
            patch("guidance.service.get_guidance_llm", return_value=FakeLlm({"bad": "payload"})),
            patch("guidance.service.logger.exception"),
        ):
            guidance, source = await generate_mi_guidance(
                result={"user_id": "user-1", "top_dimensions": ["logical_math"]},
                dimension_labels={"logical_math": "Logic / Toán học"},
                fallback_recommendations=["Thực hành bằng một bài toán đo được."],
                profile=None,
            )

        self.assertEqual(source, "deterministic_fallback")
        self.assertGreaterEqual(len(guidance.learning_strategies_vi), 2)

    async def test_alignment_narrative_cannot_override_deterministic_state(self):
        payload = {
            "executive_summary_vi": "CV có bằng chứng phù hợp, trong khi mức hứng thú cần được kiểm chứng thêm qua trải nghiệm ngắn hạn.",
            "strengths_vi": ["CV ghi nhận kỹ năng Python phù hợp với mục tiêu."],
            "watchouts_vi": ["Mức tương đồng Holland chưa cao."],
            "action_plan_vi": [
                "Hoàn thành một dự án nhỏ trong bốn tuần.",
                "Phỏng vấn một người đang làm trong vai trò mục tiêu.",
            ],
            "learning_strategy_vi": "Kết hợp sơ đồ và bài thực hành có metric.",
        }
        with (
            patch("guidance.service.get_guidance_llm", return_value=FakeLlm(payload)),
            patch("guidance.service.logger.exception"),
        ):
            narrative, source = await generate_alignment_narrative(
                profile={
                    "user_id": "user-1",
                    "target_role": "AI Engineer",
                    "target_level": "junior",
                    "total_score": 72,
                    "extracted_skills": ["Python"],
                },
                holland={"top_code": "I-A-C", "scores": {"I": 0.8, "A": 0.6}},
                mi_result={"top_dimensions": ["logical_math", "spatial"]},
                benchmark={"riasec": {"I": 1.0, "A": 0.3}},
                state="interest_conflict",
                severity="high",
                cv_score=72,
                holland_score=45,
                recommendations=["Kiểm chứng hứng thú bằng một dự án ngắn."],
            )

        self.assertEqual(source, "vertex_ai")
        self.assertFalse(hasattr(narrative, "alignment_state"))
        self.assertEqual(len(narrative.action_plan_vi), 2)

    async def test_alignment_output_with_decision_field_is_rejected(self):
        payload = {
            "executive_summary_vi": "Model cố gắng thay đổi kết luận nhưng field ngoài hợp đồng phải bị từ chối hoàn toàn.",
            "strengths_vi": [],
            "watchouts_vi": [],
            "action_plan_vi": ["Thực hiện một dự án ngắn có tiêu chí đo lường.", "Cập nhật bằng chứng mới vào CV."],
            "learning_strategy_vi": "",
            "alignment_state": "aligned",
        }
        with (
            patch("guidance.service.get_guidance_llm", return_value=FakeLlm(payload)),
            patch("guidance.service.logger.exception"),
        ):
            _, source = await generate_alignment_narrative(
                profile={"user_id": "user-1", "target_role": "AI Engineer"},
                holland={"top_code": "I-A-C", "scores": {"I": 0.8}},
                mi_result=None,
                benchmark={"riasec": {"I": 1.0}},
                state="interest_conflict",
                severity="high",
                cv_score=72,
                holland_score=45,
                recommendations=["Kiểm chứng hứng thú bằng một dự án ngắn."],
            )

        self.assertEqual(source, "deterministic_fallback")


if __name__ == "__main__":
    unittest.main()
