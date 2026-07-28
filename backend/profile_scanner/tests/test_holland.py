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
        self.assertEqual(result.assessment_version, "holland-v2")
        self.assertTrue(result.question_set_hash)

    def test_holland_scoring_is_idempotent_and_ties_are_explicit(self):
        answers = [
            HollandAnswer(question_id=question.id, score=3)
            for question in HOLLAND_QUESTIONS
        ]
        first = score_holland_answers(HollandScoreRequest(user_id="test-user", answers=answers))
        second = score_holland_answers(
            HollandScoreRequest(user_id="test-user", answers=list(reversed(answers)))
        )
        self.assertEqual(first.assessment_id, second.assessment_id)
        self.assertEqual(first.tied_top_dimensions, ["R", "I", "A", "S", "E", "C"])

    def test_partial_holland_assessment_is_rejected(self):
        with self.assertRaises(HTTPException):
            score_holland_answers(HollandScoreRequest(
                user_id="test-user",
                answers=[HollandAnswer(question_id="R1", score=3)],
            ))

    def test_holland_retake_uses_a_new_attempt_id(self):
        answers = [
            HollandAnswer(question_id=question.id, score=3)
            for question in HOLLAND_QUESTIONS
        ]
        first = score_holland_answers(
            HollandScoreRequest(user_id="test-user", answers=answers, attempt_id="attempt-1")
        )
        retake = score_holland_answers(
            HollandScoreRequest(user_id="test-user", answers=answers, attempt_id="attempt-2")
        )

        self.assertNotEqual(first.assessment_id, retake.assessment_id)


if __name__ == "__main__":
    unittest.main()
