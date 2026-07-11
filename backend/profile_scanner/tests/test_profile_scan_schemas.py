from profile_scan.schemas import ProfileRequest


def test_profile_request_defaults_target_role_to_none():
    request = ProfileRequest(user_id="test-user", cv_document_id="cv-123")

    assert request.target_role is None


def test_profile_request_accepts_target_role():
    request = ProfileRequest(
        user_id="test-user",
        cv_document_id="cv-123",
        target_role="AI Engineer",
    )

    assert request.target_role == "AI Engineer"
