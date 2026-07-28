CAPABILITIES = [
    {"id": "cv_intake", "label_vi": "Tiếp nhận CV", "requires": ["gcs", "firestore"]},
    {"id": "cv_ocr_extraction", "label_vi": "OCR và trích xuất CV", "requires": ["document_ai"]},
    {"id": "cv_profile_analysis", "label_vi": "Phân tích và benchmark CV", "requires": ["vertex_ai_optional"]},
    {"id": "canonical_profile", "label_vi": "Xác nhận và quản lý hồ sơ chuẩn", "requires": ["firestore"]},
    {"id": "holland_assessment", "label_vi": "Holland / RIASEC", "requires": ["firestore"]},
    {"id": "multiple_intelligences", "label_vi": "Đa trí thông minh", "requires": ["firestore"]},
    {"id": "career_alignment", "label_vi": "Tổng hợp CV, Holland và MI", "requires": ["firestore"]},
]
