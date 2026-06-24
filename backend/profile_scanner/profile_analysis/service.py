import asyncio
import datetime
import json
import re
import unicodedata
from typing import Any

from fastapi import HTTPException
from google.cloud import storage

from core.config import settings
from cv_intake.repository import update_cv_document
from profile_ai_extraction.service import extract_structured_profile_with_ai
from profile_ai_extraction.schemas import StructuredProfile
from profile_analysis.benchmark import (
    BENCHMARK_NOTES,
    BENCHMARK_VERSION,
    CAREER_READINESS_SIGNALS,
    DIMENSION_WEIGHTS,
    GRADE_THRESHOLDS,
    ROLE_BENCHMARKS,
    SKILL_ALIASES,
)
from profile_analysis.schemas import ProfileAnalysisResult, ScoreDimension


SECTION_PATTERNS = {
    "experience": ["experience", "work history", "employment", "kinh nghiệm", "làm việc"],
    "education": ["education", "academic", "degree", "university", "học vấn", "đại học", "cao đẳng"],
    "projects": ["project", "portfolio", "github", "dự án", "sản phẩm"],
    "skills": ["skills", "technical skills", "tools", "kỹ năng", "công cụ"],
}

ACTION_VERBS = [
    "built", "developed", "implemented", "created", "launched", "led", "owned",
    "optimized", "improved", "reduced", "increased", "automated", "analyzed",
    "designed", "deployed", "xây dựng", "phát triển", "triển khai", "tối ưu",
    "phân tích", "thiết kế", "cải thiện",
]

CERTIFICATION_KEYWORDS = [
    "certificate", "certification", "google career certificate", "aws certified",
    "coursera", "udemy", "edx", "datacamp", "freecodecamp", "chứng chỉ", "khóa học",
]


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def split_lines(text: str) -> list[str]:
    return [line.strip(" -•\t") for line in text.splitlines() if line.strip(" -•\t")]


def unique_keep_order(items: list[str], limit: int | None = None) -> list[str]:
    seen = set()
    result = []
    for item in items:
        normalized = normalize_text(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(item)
        if limit and len(result) >= limit:
            break
    return result


def compact_parts(parts: list[str]) -> str:
    return " | ".join(part.strip() for part in parts if part and part.strip())


def contains_any(normalized_text: str, keywords: list[str]) -> bool:
    for keyword in keywords:
        normalized_keyword = normalize_text(keyword)
        if not normalized_keyword:
            continue
        if len(normalized_keyword) <= 3 and re.fullmatch(r"[a-z0-9+#.]+", normalized_keyword):
            pattern = rf"(?<![a-z0-9+#.]){re.escape(normalized_keyword)}(?![a-z0-9+#.])"
            if re.search(pattern, normalized_text):
                return True
        elif normalized_keyword in normalized_text:
            return True
    return False


def extract_matching_skills(text: str) -> list[str]:
    normalized = normalize_text(text)
    matches = []
    for skill, aliases in SKILL_ALIASES.items():
        if contains_any(normalized, aliases):
            matches.append(skill)
    return sorted(matches)


def detect_target_role(text: str, target_role: str | None = None, message: str | None = None) -> tuple[str, dict]:
    haystack = normalize_text(" ".join(part for part in [target_role, message, text[:4000]] if part))
    best_slug = "general_early_career"
    best_score = 0

    for slug, benchmark in ROLE_BENCHMARKS.items():
        score = 0
        for alias in benchmark["aliases"]:
            if normalize_text(alias) in haystack:
                score += 3
        for skill in benchmark["core_skills"]:
            if skill in extract_matching_skills(haystack):
                score += 1
        if score > best_score:
            best_slug = slug
            best_score = score

    return best_slug, ROLE_BENCHMARKS[best_slug]


def extract_relevant_lines(text: str, keywords: list[str], limit: int = 6) -> list[str]:
    normalized_keywords = [normalize_text(keyword) for keyword in keywords]
    result = []
    for line in split_lines(text):
        normalized_line = normalize_text(line)
        if any(keyword in normalized_line for keyword in normalized_keywords):
            result.append(line)
    return unique_keep_order(result, limit)


def extract_work_experience_lines(text: str) -> list[str]:
    date_pattern = re.compile(r"\b(20\d{2}|19\d{2})\b|\b\d+\+?\s*(years?|yrs?|năm)\b", re.IGNORECASE)
    role_pattern = re.compile(
        r"\b(engineer|developer|analyst|intern|manager|designer|consultant|assistant|specialist|"
        r"thực tập|kỹ sư|lập trình|phân tích|nhân viên)\b",
        re.IGNORECASE,
    )
    lines = []
    for line in split_lines(text):
        if date_pattern.search(line) or role_pattern.search(line):
            lines.append(line)
    return unique_keep_order(lines, 8)


def extract_project_lines(text: str) -> list[str]:
    keywords = SECTION_PATTERNS["projects"] + [
        "dashboard", "website", "app", "model", "pipeline", "api", "analysis", "case study"
    ]
    return extract_relevant_lines(text, keywords, 8)


def extract_education_lines(text: str) -> list[str]:
    keywords = SECTION_PATTERNS["education"] + [
        "bachelor", "master", "gpa", "major", "minor", "computer science",
        "software", "data", "business", "cử nhân", "thạc sĩ", "ngành", "khoa"
    ]
    return extract_relevant_lines(text, keywords, 6)


def count_quantified_achievements(text: str) -> int:
    patterns = [
        r"\b\d+(\.\d+)?\s*%",
        r"\b\d+(\.\d+)?\s*(users?|customers?|clients?|records?|rows?|hours?|days?|seconds?|requests?)\b",
        r"\b\d+(\.\d+)?\s*(người dùng|khách hàng|bản ghi|giờ|ngày)\b",
        r"\$\s?\d+",
    ]
    return sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in patterns)


def score_role_skill_fit(skills: list[str], benchmark: dict) -> ScoreDimension:
    core_skills = benchmark["core_skills"]
    supporting_skills = benchmark["supporting_skills"]
    matched_core = [skill for skill in core_skills if skill in skills]
    matched_supporting = [skill for skill in supporting_skills if skill in skills]
    core_score = len(matched_core) / max(len(core_skills), 1) * 75
    supporting_score = len(matched_supporting) / max(len(supporting_skills), 1) * 25
    score = min(100, core_score + supporting_score)
    missing = [skill for skill in core_skills if skill not in matched_core]

    return ScoreDimension(
        key="role_skill_fit",
        label="Role skill fit",
        score=round(score, 2),
        weight=DIMENSION_WEIGHTS["role_skill_fit"],
        evidence=matched_core + matched_supporting,
        missing=missing,
    )


def score_experience_evidence(text: str, work_lines: list[str], project_lines: list[str]) -> ScoreDimension:
    normalized = normalize_text(text)
    action_hits = [verb for verb in ACTION_VERBS if normalize_text(verb) in normalized]
    quantified_count = count_quantified_achievements(text)
    score = 20
    score += min(len(work_lines), 4) * 10
    score += min(len(project_lines), 4) * 8
    score += min(len(action_hits), 8) * 3
    score += min(quantified_count, 5) * 5
    score = min(100, score)

    evidence = []
    if work_lines:
        evidence.append(f"{len(work_lines)} experience-related lines detected")
    if project_lines:
        evidence.append(f"{len(project_lines)} project/portfolio lines detected")
    if quantified_count:
        evidence.append(f"{quantified_count} quantified impact signals")
    if action_hits:
        evidence.append(f"Action verbs: {', '.join(action_hits[:6])}")

    missing = []
    if not work_lines:
        missing.append("No clear work/internship experience section detected")
    if quantified_count == 0:
        missing.append("No quantified achievement or measurable impact detected")
    if not project_lines:
        missing.append("No clear project or portfolio evidence detected")

    return ScoreDimension(
        key="experience_evidence",
        label="Experience and evidence",
        score=round(score, 2),
        weight=DIMENSION_WEIGHTS["experience_evidence"],
        evidence=evidence,
        missing=missing,
    )


def score_education_certification(text: str, education_lines: list[str], benchmark: dict) -> ScoreDimension:
    normalized = normalize_text(text)
    degree_hit = contains_any(normalized, ["bachelor", "master", "degree", "university", "college", "cử nhân", "thạc sĩ", "đại học"])
    cert_hits = [keyword for keyword in CERTIFICATION_KEYWORDS if normalize_text(keyword) in normalized]
    field_hit = contains_any(normalized, benchmark.get("education_keywords", []))

    score = 35
    if degree_hit:
        score += 30
    if field_hit:
        score += 20
    if cert_hits:
        score += 15
    if education_lines and not degree_hit:
        score += 10
    score = min(100, score)

    missing = []
    if not degree_hit:
        missing.append("No explicit degree/university signal detected")
    if not field_hit:
        missing.append("Education field is not clearly aligned with target role")
    if not cert_hits:
        missing.append("No certification/course signal detected")

    return ScoreDimension(
        key="education_certification",
        label="Education and certification",
        score=round(score, 2),
        weight=DIMENSION_WEIGHTS["education_certification"],
        evidence=education_lines[:3] + cert_hits[:3],
        missing=missing,
    )


def score_career_readiness(text: str) -> ScoreDimension:
    normalized = normalize_text(text)
    matched = []
    missing = []
    for competency, keywords in CAREER_READINESS_SIGNALS.items():
        if contains_any(normalized, keywords):
            matched.append(competency)
        else:
            missing.append(competency)

    score = len(matched) / max(len(CAREER_READINESS_SIGNALS), 1) * 100
    return ScoreDimension(
        key="career_readiness",
        label="Career-readiness signals",
        score=round(score, 2),
        weight=DIMENSION_WEIGHTS["career_readiness"],
        evidence=matched,
        missing=missing[:4],
    )


def score_cv_clarity(text: str, skills: list[str]) -> ScoreDimension:
    normalized = normalize_text(text)
    lines = split_lines(text)
    evidence = []
    score = 25

    if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text):
        score += 12
        evidence.append("email")
    if "linkedin" in normalized:
        score += 10
        evidence.append("linkedin")
    if "github" in normalized or "portfolio" in normalized:
        score += 10
        evidence.append("portfolio/github")
    section_hits = [section for section, keywords in SECTION_PATTERNS.items() if contains_any(normalized, keywords)]
    score += min(len(section_hits), 4) * 8
    if len(skills) >= 5:
        score += 10
        evidence.append("clear skill inventory")
    if 900 <= len(text) <= 7000:
        score += 8
        evidence.append("reasonable CV text length")
    if len(lines) >= 20:
        score += 5
        evidence.append("structured line breaks")
    score = min(100, score)

    missing = []
    if "email" not in evidence:
        missing.append("No email detected")
    if "linkedin" not in evidence:
        missing.append("No LinkedIn signal detected")
    if "portfolio/github" not in evidence:
        missing.append("No portfolio/GitHub signal detected")
    for section in ["experience", "education", "projects", "skills"]:
        if section not in section_hits:
            missing.append(f"No clear {section} section detected")

    return ScoreDimension(
        key="cv_clarity",
        label="CV clarity and ATS completeness",
        score=round(score, 2),
        weight=DIMENSION_WEIGHTS["cv_clarity"],
        evidence=evidence + section_hits,
        missing=missing[:5],
    )


def compute_total_score(dimensions: list[ScoreDimension]) -> float:
    total = sum(dimension.score * dimension.weight for dimension in dimensions)
    return round(total, 2)


def grade_from_score(score: float) -> str:
    for grade, threshold in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "E"


def build_strengths(dimensions: list[ScoreDimension], skills: list[str]) -> list[str]:
    strengths = []
    for dimension in dimensions:
        if dimension.score >= 75 and dimension.evidence:
            strengths.append(f"{dimension.label}: {', '.join(dimension.evidence[:4])}")
    if skills:
        strengths.insert(0, f"Detected skills: {', '.join(skills[:10])}")
    return strengths[:6]


def build_recommendations(dimensions: list[ScoreDimension]) -> list[str]:
    recommendations = []
    for dimension in sorted(dimensions, key=lambda item: item.score):
        if dimension.missing:
            recommendations.append(f"Improve {dimension.label}: {dimension.missing[0]}.")
    return recommendations[:5]


def profile_lines_from_ai(structured_profile: StructuredProfile | None) -> tuple[list[str], list[str], list[str], list[str]]:
    if not structured_profile:
        return [], [], [], []

    work_lines = [
        compact_parts([
            item.title,
            item.organization,
            item.duration,
            item.summary,
            "; ".join(item.impact_evidence[:2]),
        ])
        for item in structured_profile.work_experiences
    ]
    education_lines = [
        compact_parts([
            item.degree,
            item.field,
            item.institution,
            item.duration,
            item.evidence,
        ])
        for item in structured_profile.education
    ]
    project_lines = [
        compact_parts([
            item.name,
            item.summary,
            ", ".join(item.skills[:6]),
            "; ".join(item.impact_evidence[:2]),
            item.url,
        ])
        for item in structured_profile.projects
    ]
    achievement_lines = structured_profile.achievements + structured_profile.certifications
    return (
        unique_keep_order([line for line in work_lines if line], 8),
        unique_keep_order([line for line in education_lines if line], 6),
        unique_keep_order([line for line in project_lines if line], 8),
        unique_keep_order([line for line in achievement_lines if line], 8),
    )


def skills_from_ai(structured_profile: StructuredProfile | None) -> list[str]:
    if not structured_profile:
        return []

    skills = list(structured_profile.skills)
    for item in structured_profile.work_experiences:
        skills.extend(item.skills)
    for item in structured_profile.projects:
        skills.extend(item.skills)
    return unique_keep_order([skill.strip().lower() for skill in skills if skill.strip()])


def career_readiness_text_from_ai(structured_profile: StructuredProfile | None) -> str:
    if not structured_profile:
        return ""
    return " ".join(structured_profile.career_readiness_signals + structured_profile.achievements)


def build_message(grade: str, score: float, benchmark_label: str) -> str:
    return (
        f"Profile Scanner đã phân tích CV theo benchmark {benchmark_label}. "
        f"Kết quả hiện tại là rank {grade} với {score}/100 điểm. "
        "Điểm này dựa trên kỹ năng phù hợp vai trò, bằng chứng kinh nghiệm, học vấn/chứng chỉ, "
        "tín hiệu career-readiness và độ rõ ràng của CV."
    )


def build_artifact_object_name(original_object: str, filename: str) -> str:
    prefix = original_object.rsplit("/", 1)[0]
    return f"{prefix}/{filename}"


def download_text_artifact(bucket: Any, object_name: str) -> str:
    return bucket.blob(object_name).download_as_text(encoding="utf-8")


def upload_json_artifact(bucket: Any, object_name: str, payload: dict) -> str:
    blob = bucket.blob(object_name)
    blob.upload_from_string(
        json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        content_type="application/json; charset=utf-8",
    )
    return f"gs://{bucket.name}/{object_name}"


async def analyze_cv_profile(document: dict) -> ProfileAnalysisResult:
    existing = document.get("profile_analysis")
    can_reuse_existing = (
        existing
        and document.get("analysis_status") == "completed"
        and existing.get("benchmark_version") == BENCHMARK_VERSION
        and (
            not settings.profile_ai_extraction_enabled
            or existing.get("ai_extraction_used") is True
        )
    )
    if can_reuse_existing:
        return ProfileAnalysisResult(**existing)

    cv_document_id = document["cv_document_id"]
    bucket_name = document.get("storage_bucket")
    parsed_text_object = document.get("parsed_text_object")
    original_object = document.get("storage_object")
    if not bucket_name or not parsed_text_object or not original_object:
        raise HTTPException(status_code=400, detail="Parsed CV text metadata is incomplete.")

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    try:
        parsed_text = download_text_artifact(bucket, parsed_text_object)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Unable to load parsed CV text from GCS.") from exc

    structured_profile = await asyncio.to_thread(
        extract_structured_profile_with_ai,
        parsed_text=parsed_text,
        target_role=document.get("target_role"),
        message=document.get("message"),
    )

    skills = unique_keep_order(extract_matching_skills(parsed_text) + skills_from_ai(structured_profile))
    target_slug, benchmark = detect_target_role(
        parsed_text,
        target_role=document.get("target_role") or (structured_profile.target_role_hint if structured_profile else None),
        message=document.get("message"),
    )
    ai_work_lines, ai_education_lines, ai_project_lines, ai_achievement_lines = profile_lines_from_ai(structured_profile)
    work_lines = unique_keep_order(ai_work_lines + extract_work_experience_lines(parsed_text), 8)
    project_lines = unique_keep_order(ai_project_lines + extract_project_lines(parsed_text), 8)
    education_lines = unique_keep_order(ai_education_lines + extract_education_lines(parsed_text), 6)
    scoring_text = compact_parts([
        parsed_text,
        career_readiness_text_from_ai(structured_profile),
        "\n".join(ai_achievement_lines),
    ])

    dimensions = [
        score_role_skill_fit(skills, benchmark),
        score_experience_evidence(scoring_text, work_lines, project_lines),
        score_education_certification(scoring_text, education_lines, benchmark),
        score_career_readiness(scoring_text),
        score_cv_clarity(parsed_text, skills),
    ]
    total_score = compute_total_score(dimensions)
    grade = grade_from_score(total_score)
    analyzed_at = utc_now()

    missing_signals = unique_keep_order(
        [missing for dimension in dimensions for missing in dimension.missing],
        10,
    )
    result = ProfileAnalysisResult(
        cv_document_id=cv_document_id,
        target_role=benchmark["label"],
        benchmark_profile_id=target_slug,
        benchmark_version=BENCHMARK_VERSION,
        grade=grade,
        total_score=total_score,
        score_dimensions=dimensions,
        extracted_skills=skills,
        work_experiences=work_lines,
        education_records=education_lines,
        projects=project_lines,
        strengths=build_strengths(dimensions, skills),
        weaknesses=[
            f"{dimension.label}: {dimension.score}/100"
            for dimension in dimensions
            if dimension.score < 65
        ],
        missing_signals=missing_signals,
        recommendations=build_recommendations(dimensions),
        benchmark_notes=BENCHMARK_NOTES,
        ai_extraction_used=structured_profile is not None,
        ai_extraction_confidence=structured_profile.confidence if structured_profile else None,
        structured_profile=structured_profile.as_firestore_payload() if structured_profile else None,
        analyzed_at=analyzed_at,
        message_vi=build_message(grade, total_score, benchmark["label"]),
    )

    analysis_object = build_artifact_object_name(original_object, "profile_analysis.json")
    analysis_uri = f"gs://{bucket.name}/{analysis_object}"
    result.analysis_artifact_gcs_uri = analysis_uri
    upload_json_artifact(bucket, analysis_object, result.as_firestore_payload())

    await update_cv_document(cv_document_id, {
        "analysis_status": "completed",
        "profile_analysis": result.as_firestore_payload(),
        "analysis_object": analysis_object,
        "analysis_gcs_uri": analysis_uri,
        "grade": grade,
        "total_score": total_score,
        "target_role": result.target_role,
        "benchmark_profile_id": target_slug,
        "benchmark_version": BENCHMARK_VERSION,
        "ai_extraction_used": structured_profile is not None,
        "ai_extraction_confidence": structured_profile.confidence if structured_profile else None,
        "structured_profile": structured_profile.as_firestore_payload() if structured_profile else None,
        "analyzed_at": analyzed_at,
        "next_status": "analysis_completed",
    })

    return result
