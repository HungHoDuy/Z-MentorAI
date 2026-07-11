import unittest

from fastapi import HTTPException

from holland.questions import HOLLAND_QUESTIONS
from holland.schemas import HollandAnswer, HollandScoreRequest
from holland.service import score_holland_answers


class HollandAssessmentTests(unittest.TestCase):
    def test_complete_holland_assessment_is_scored(self):
        answers = [
            HollandAnswer(question_id=question.id, score=5 if question.dimension == "I" else 2)
            for question in HOLLAND_QUESTIONS
        ]
        result = score_holland_answers(HollandScoreRequest(user_id="test-user", answers=answers))
        self.assertEqual(result.answered_count, len(HOLLAND_QUESTIONS))
        self.assertTrue(result.top_code.startswith("I"))

    def test_partial_holland_assessment_is_rejected(self):
        with self.assertRaises(HTTPException):
            score_holland_answers(HollandScoreRequest(
                user_id="test-user",
                answers=[HollandAnswer(question_id="R1", score=3)],
            ))


if __name__ == "__main__":
    unittest.main()
