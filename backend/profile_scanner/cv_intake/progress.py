PRODUCT_STAGES = [
    ("review_cv", "Đọc và kiểm tra CV", "Read and check CV"),
    ("confirm_profile", "Xác nhận thông tin hồ sơ", "Confirm profile information"),
    ("confirm_target", "Xác định mục tiêu ứng tuyển", "Confirm application target"),
    ("evaluate_fit", "Đánh giá mức độ phù hợp", "Evaluate role fit"),
    ("complete_result", "Hoàn thiện kết quả", "Complete results"),
]

INTERNAL_TO_PRODUCT_STAGE = {
    "pending": "review_cv",
    "extracting_cv": "review_cv",
    "draft_ready": "confirm_profile",
    "draft_confirmed": "confirm_target",
    "awaiting_target_level": "confirm_target",
    "analyzing_profile": "evaluate_fit",
    "loading_benchmark": "evaluate_fit",
    "scoring_profile": "evaluate_fit",
    "building_feedback": "complete_result",
    "preparing_canonical_profile": "complete_result",
    "completed": "complete_result",
}


def processing_steps(current_stage: str) -> list[dict]:
    product_stage = INTERNAL_TO_PRODUCT_STAGE.get(current_stage, "review_cv")
    stage_keys = [key for key, _, _ in PRODUCT_STAGES]
    current_index = stage_keys.index(product_stage)
    waiting_stages = {"draft_ready", "awaiting_target_level"}
    return [
        {
            "key": key,
            "label_vi": label_vi,
            "label_en": label_en,
            "status": (
                "completed" if index < current_index or current_stage == "completed"
                else "waiting_user" if key == product_stage and current_stage in waiting_stages
                else "running" if key == product_stage
                else "pending"
            ),
        }
        for index, (key, label_vi, label_en) in enumerate(PRODUCT_STAGES)
    ]
