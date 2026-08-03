import unittest

from cv_intake.progress import processing_steps


class CvProgressTests(unittest.TestCase):
    def test_internal_stages_are_grouped_into_product_phases(self):
        steps = processing_steps("loading_benchmark")

        self.assertEqual(len(steps), 5)
        self.assertEqual(steps[0]["label_vi"], "Đọc và kiểm tra CV")
        self.assertEqual(steps[3]["label_vi"], "Đánh giá mức độ phù hợp")
        self.assertEqual(steps[3]["status"], "running")
        self.assertNotIn("benchmark", " ".join(step["label_vi"].lower() for step in steps))

    def test_waiting_stage_uses_user_confirmation_status(self):
        steps = processing_steps("draft_ready")

        self.assertEqual(steps[1]["status"], "waiting_user")
        self.assertEqual(steps[2]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
