import re
import unicodedata

from profile_ai_extraction.schemas import StructuredProfile


TARGET_LEVELS = ("intern", "fresher", "junior", "middle", "senior", "lead", "manager")
LEVEL_LABELS_VI = {
    "intern": "Thực tập sinh",
    "fresher": "Fresher",
    "junior": "Junior",
    "middle": "Middle",
    "senior": "Senior",
    "lead": "Lead",
    "manager": "Quản lý",
}


def _normalize(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return "".join(ch for ch in text if not unicodedata.combining(ch)).lower()


def normalize_target_level(value: str | None) -> str | None:
    text = _normalize(value)
    patterns = (
        ("manager", r"\b(manager|director|head of|truong phong|quan ly)\b"),
        ("lead", r"\b(tech lead|team lead|lead engineer|lead developer|lead)\b"),
        ("senior", r"\b(senior|principal|staff engineer|architect)\b"),
        ("middle", r"\b(mid[- ]?level|middle|intermediate)\b"),
        ("junior", r"\b(junior|entry[- ]?level)\b"),
        ("fresher", r"\b(fresher|new graduate|graduate)\b"),
        ("intern", r"\b(intern|internship|thuc tap)\b"),
    )
    for level, pattern in patterns:
        if re.search(pattern, text):
            return level
    return None


def infer_current_level(profile: StructuredProfile | None) -> tuple[str | None, float, list[str]]:
    if profile is None:
        return None, 0.0, []

    titles = " | ".join(item.title for item in profile.work_experiences if item.title)
    explicit = normalize_target_level(titles)
    if explicit:
        return explicit, 0.9, [f"Chức danh trong CV: {titles[:180]}"]

    experience_count = len(profile.work_experiences)
    evidence = []
    if experience_count:
        evidence.append(f"CV có {experience_count} mục kinh nghiệm làm việc.")
    if experience_count >= 4:
        return "senior", 0.55, evidence
    if experience_count >= 2:
        return "middle", 0.5, evidence
    if experience_count == 1:
        return "junior", 0.45, evidence

    education_text = " | ".join(
        f"{item.degree} {item.field} {item.duration}" for item in profile.education
    )
    if re.search(r"\b(student|undergraduate|sinh vien)\b", _normalize(education_text)):
        return "intern", 0.5, ["CV thể hiện ứng viên đang là sinh viên."]
    return None, 0.0, evidence


def level_options() -> list[dict[str, str]]:
    return [{"value": level, "label_vi": LEVEL_LABELS_VI[level]} for level in TARGET_LEVELS]
