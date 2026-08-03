import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from profile_ai_extraction.schemas import StructuredProfile
from profile_ai_extraction.service import (
    extract_structured_profile_with_ai,
    revise_structured_profile_with_ai,
)


def test_structured_profile_uses_defaults_for_null_model_fields():
    profile = StructuredProfile(
        full_name="Candidate",
        email=None,
        headline=None,
        skills=["Python", None],
        projects=[
            {
                "name": "AI Assistant",
                "url": None,
                "skills": ["Python", None],
            }
        ],
        confidence=0.9,
    )

    assert profile.email == ""
    assert profile.headline == ""
    assert profile.skills == ["Python"]
    assert profile.projects[0].url == ""
    assert profile.projects[0].skills == ["Python"]


def test_structured_profile_accepts_localizable_profile_issues():
    profile = StructuredProfile(
        full_name="Candidate",
        profile_issues=[
            {"field": "email", "code": "missing", "severity": "warning"},
            {"field": "location", "code": "unclear", "severity": "info"},
        ],
    )

    assert profile.profile_issues[0].field == "email"
    assert profile.as_firestore_payload()["profile_issues"][1]["code"] == "unclear"


class ProfileAiExtractionTests(unittest.TestCase):
    def test_extraction_and_revision_use_separate_prompts(self):
        extraction_payload = {
            "full_name": "Nguyen Van A",
            "skills": ["Python"],
            "confidence": 0.8,
        }
        revision_payload = {
            "full_name": "Nguyen Van An",
            "skills": ["Python"],
            "confidence": 0.8,
        }
        fake_llm = SimpleNamespace()
        fake_llm.invoke = lambda messages: SimpleNamespace(
            content=json.dumps(
                revision_payload
                if "Apply the correction" in str(messages[-1].content)
                else extraction_payload
            )
        )
        with patch("profile_ai_extraction.service.get_profile_extraction_llm", return_value=fake_llm):
            extracted = extract_structured_profile_with_ai(parsed_text="Nguyen Van A\nPython")
            revised = revise_structured_profile_with_ai(
                current_profile=extracted,
                instruction="Tên đầy đủ là Nguyen Van An",
            )
        self.assertEqual(extracted.full_name, "Nguyen Van A")
        self.assertEqual(extracted.extraction_source, "ai")
        self.assertEqual(revised.full_name, "Nguyen Van An")
        self.assertEqual(revised.extraction_source, "user_correction_ai_mapped")


if __name__ == "__main__":
    unittest.main()
