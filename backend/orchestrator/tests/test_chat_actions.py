import json
import unittest

from fastapi import HTTPException

from chat_actions import build_structured_tool_request


class ChatActionTests(unittest.TestCase):
    def test_holland_submit_routes_without_llm(self):
        request = build_structured_tool_request({
            "type": "assessment.submit",
            "assessment_type": "holland_riasec",
            "attempt_id": "attempt-1",
            "question_set_hash": "hash-1",
            "answers": [{"question_id": "R1", "score": 5}],
        }, "google-user")
        self.assertEqual(request["tool"], "profile_scanner")
        self.assertEqual(request["input"]["user_id"], "google-user")
        self.assertEqual(request["input"]["task"], "holland_score")
        self.assertEqual(json.loads(request["input"]["answers_json"])[0]["score"], 5)

    def test_cv_draft_action_never_accepts_user_id_from_payload(self):
        request = build_structured_tool_request({
            "type": "cv_draft.confirm",
            "user_id": "attacker",
            "cv_document_id": "cv-1",
            "extraction_id": "draft-1",
        }, "authenticated-user")
        self.assertEqual(request["input"]["user_id"], "authenticated-user")
        self.assertEqual(request["input"]["task"], "cv_draft_confirm")

    def test_profile_save_decision_routes_without_llm(self):
        request = build_structured_tool_request({
            "type": "profile.save_decision",
            "user_id": "attacker",
            "cv_document_id": "cv-1",
            "decision": "update",
        }, "authenticated-user")
        self.assertEqual(request["input"], {
            "user_id": "authenticated-user",
            "task": "profile_confirm",
            "cv_document_id": "cv-1",
            "decision": "update",
        })

    def test_invalid_score_is_rejected(self):
        with self.assertRaises(HTTPException):
            build_structured_tool_request({
                "type": "assessment.submit",
                "assessment_type": "multiple_intelligences",
                "answers": [{"question_id": "L1", "score": 6}],
            }, "user")


if __name__ == "__main__":
    unittest.main()
