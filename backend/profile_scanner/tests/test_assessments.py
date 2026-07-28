import unittest

from fastapi import HTTPException

from assessments.definitions import MULTIPLE_INTELLIGENCES
from assessments.schemas import AssessmentAnswer, AssessmentScoreRequest
from assessments.service import get_assessment_definition, score_assessment_answers


class AssessmentTests(unittest.TestCase):
    def test_multiple_intelligences_aliases_resolve(self):
        self.assertEqual(
            get_assessment_definition("mi").assessment_type,
            "multiple_intelligences",
        )
        self.assertEqual(
            get_assessment_definition("multiple_intelligence").assessment_type,
            "multiple_intelligences",
        )

    def test_multiple_intelligences_scores_top_dimension(self):
        answers = []
        for question in MULTIPLE_INTELLIGENCES.questions:
            score = 5 if question.dimension == "logical_math" else 1
            answers.append(AssessmentAnswer(question_id=question.id, score=score))

        result = score_assessment_answers(
            "multiple_intelligences",
            AssessmentScoreRequest(user_id="test-user", answers=answers),
        )

        self.assertEqual(result.assessment_type, "multiple_intelligences")
        self.assertEqual(result.top_dimensions[0], "logical_math")
        self.assertEqual(result.answered_count, len(MULTIPLE_INTELLIGENCES.questions))
        self.assertFalse(result.missing_question_ids)
        duplicate = score_assessment_answers(
            "multiple_intelligences",
            AssessmentScoreRequest(user_id="test-user", answers=list(reversed(answers))),
        )
        self.assertEqual(result.assessment_id, duplicate.assessment_id)
        self.assertTrue(result.question_set_hash)

    def test_unknown_question_id_rejected(self):
        with self.assertRaises(HTTPException):
            score_assessment_answers(
                "multiple_intelligences",
                AssessmentScoreRequest(
                    user_id="test-user",
                    answers=[AssessmentAnswer(question_id="NOPE", score=3)],
                ),
            )

    def test_partial_assessment_is_rejected(self):
        with self.assertRaises(HTTPException):
            score_assessment_answers(
                "multiple_intelligences",
                AssessmentScoreRequest(
                    user_id="test-user",
                    answers=[AssessmentAnswer(question_id="L1", score=3)],
                ),
            )

    def test_equal_scores_report_tied_dimensions(self):
        answers = [
            AssessmentAnswer(question_id=question.id, score=3)
            for question in MULTIPLE_INTELLIGENCES.questions
        ]
        result = score_assessment_answers(
            "multiple_intelligences",
            AssessmentScoreRequest(user_id="test-user", answers=answers),
        )
        self.assertEqual(
            result.tied_top_dimensions,
            list(MULTIPLE_INTELLIGENCES.dimension_labels.keys()),
        )
        self.assertEqual(result.score_margin, 0.0)

    def test_retake_uses_a_new_attempt_id_but_retries_remain_idempotent(self):
        answers = [
            AssessmentAnswer(question_id=question.id, score=3)
            for question in MULTIPLE_INTELLIGENCES.questions
        ]
        first = score_assessment_answers(
            "multiple_intelligences",
            AssessmentScoreRequest(user_id="test-user", answers=answers, attempt_id="attempt-1"),
        )
        retry = score_assessment_answers(
            "multiple_intelligences",
            AssessmentScoreRequest(user_id="test-user", answers=answers, attempt_id="attempt-1"),
        )
        retake = score_assessment_answers(
            "multiple_intelligences",
            AssessmentScoreRequest(user_id="test-user", answers=answers, attempt_id="attempt-2"),
        )

        self.assertEqual(first.assessment_id, retry.assessment_id)
        self.assertNotEqual(first.assessment_id, retake.assessment_id)


if __name__ == "__main__":
    unittest.main()
