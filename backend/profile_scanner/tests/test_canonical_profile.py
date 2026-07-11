import unittest

from canonical_profile.service import build_profile_action, identity_match_score


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

    def test_email_and_name_allow_auto_update(self):
        existing = {"identity": {"full_name": "Nguyen Van A", "email": "a@example.com"}}
        action = build_profile_action(
            existing_profile=existing,
            candidate_identity={"full_name": "Nguyễn Văn A", "email": "A@example.com"},
            cv_document_id="cv-2",
        )
        self.assertEqual(action["action_required"], "auto_update_profile")
        self.assertGreaterEqual(action["identity_match_score"], 0.8)

    def test_conflicting_email_requires_overwrite_confirmation(self):
        existing = {"identity": {"full_name": "Nguyen Van A", "email": "old@example.com"}}
        action = build_profile_action(
            existing_profile=existing,
            candidate_identity={"full_name": "Different Person", "email": "new@example.com"},
            cv_document_id="cv-3",
        )
        self.assertEqual(action["action_required"], "confirm_profile_overwrite")


if __name__ == "__main__":
    unittest.main()
