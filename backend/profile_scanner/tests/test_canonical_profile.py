import unittest
from unittest.mock import AsyncMock, patch

from canonical_profile.service import (
    build_canonical_payload,
    build_profile_action,
    identity_match_score,
    prepare_profile_action,
)


class CanonicalProfileTests(unittest.TestCase):
    def test_first_cv_requires_confirmation(self):
        action = build_profile_action(
            existing_profile=None,
            candidate_identity={"full_name": "Nguyen Van A", "email": "a@example.com"},
            cv_document_id="cv-1",
        )
        self.assertEqual(action["action_required"], "confirm_profile_creation")
        self.assertEqual([item["decision"] for item in action["options"]], ["accept", "reject"])

    def test_name_only_never_auto_updates(self):
        existing = {"identity": {"full_name": "Nguyen Van A"}}
        score, signals = identity_match_score(existing, {"full_name": "Nguyễn Văn A"})
        self.assertEqual(score, 0.35)
        self.assertIn("full_name_match", signals)
        action = build_profile_action(
            existing_profile=existing,
            candidate_identity={"full_name": "Nguyễn Văn A"},
            cv_document_id="cv-2",
        )
        self.assertEqual(action["action_required"], "confirm_profile_overwrite")

    def test_email_and_name_still_require_explicit_update(self):
        existing = {"identity": {"full_name": "Nguyen Van A", "email": "a@example.com"}}
        action = build_profile_action(
            existing_profile=existing,
            candidate_identity={"full_name": "Nguyễn Văn A", "email": "A@example.com"},
            cv_document_id="cv-2",
        )
        self.assertEqual(action["action_required"], "confirm_profile_update")
        self.assertEqual([item["decision"] for item in action["options"]], ["update", "reject"])
        self.assertGreaterEqual(action["identity_match_score"], 0.8)

    def test_conflicting_email_requires_overwrite_confirmation(self):
        existing = {"identity": {"full_name": "Nguyen Van A", "email": "old@example.com"}}
        action = build_profile_action(
            existing_profile=existing,
            candidate_identity={"full_name": "Different Person", "email": "new@example.com"},
            cv_document_id="cv-3",
        )
        self.assertEqual(action["action_required"], "confirm_profile_overwrite")

    def test_canonical_fingerprint_changes_when_scoring_changes(self):
        base_analysis = {
            "candidate_identity": {"full_name": "Nguyen Van A"},
            "target_role": "AI Engineer",
            "benchmark_profile_id": "benchmark-1",
            "benchmark_version": "v1",
            "scoring_version": "score-v1",
            "skill_normalization_version": "skills-v1",
            "normalized_skills": [{"skill_id": "python"}],
            "total_score": 60,
            "grade": "C",
        }
        first = build_canonical_payload(
            user_id="user-1",
            cv_document_id="cv-1",
            analysis=base_analysis,
            previous_profile=None,
        )
        second = build_canonical_payload(
            user_id="user-1",
            cv_document_id="cv-1",
            analysis={**base_analysis, "total_score": 70, "grade": "B"},
            previous_profile=first,
        )
        self.assertNotEqual(first["analysis_fingerprint"], second["analysis_fingerprint"])
        self.assertEqual(second["schema_version"], "canonical-profile-v2")


class CanonicalProfileActionTests(unittest.IsolatedAsyncioTestCase):
    @patch("canonical_profile.service.save_profile_version", new_callable=AsyncMock)
    @patch("canonical_profile.service.mark_profile_decision", new_callable=AsyncMock)
    @patch("canonical_profile.service.get_canonical_profile", new_callable=AsyncMock)
    async def test_matching_identity_never_saves_without_user_decision(
        self,
        get_profile,
        mark_decision,
        save_profile,
    ):
        get_profile.return_value = {
            "user_id": "user-1",
            "identity": {"full_name": "Nguyen Van A", "email": "a@example.com"},
            "profile_version": 1,
        }
        document = {"user_id": "user-1", "cv_document_id": "cv-2"}
        analysis = {
            "candidate_identity": {"full_name": "Nguyen Van A", "email": "a@example.com"},
            "structured_profile": {},
            "education_records": [],
            "work_experiences": [],
        }

        action = await prepare_profile_action(document, analysis)

        self.assertEqual(action["action_required"], "confirm_profile_update")
        self.assertEqual([item["decision"] for item in action["options"]], ["update", "reject"])
        save_profile.assert_not_awaited()
        mark_decision.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
