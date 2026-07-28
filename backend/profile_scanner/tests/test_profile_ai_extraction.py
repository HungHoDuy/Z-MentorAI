from profile_ai_extraction.schemas import StructuredProfile


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
