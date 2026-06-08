from profile_scan.schemas import ProfileRequest


def analyze_profile(request: ProfileRequest) -> str:
    return (
        f"Mocked profile analysis for user {request.user_id} with background: "
        f"{request.background_info}. Found key strengths in technical skills. "
        "If the user needs career-interest alignment, run the Holland/RIASEC assessment."
    )
