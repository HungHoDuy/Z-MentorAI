import asyncio
import datetime
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException
from google.cloud import storage

from core.config import logger, settings
from cv_intake.repository import update_cv_document
from dynamic_benchmark.compiler import (
    DYNAMIC_BENCHMARK_NOTES,
    DYNAMIC_BENCHMARK_VERSION,
    compile_dynamic_benchmark,
    infer_level,
)
from dynamic_benchmark.schemas import DynamicBenchmarkSnapshot
from profile_ai_extraction.service import extract_structured_profile_with_ai
from skill_normalization.service import display_name, normalize_key, normalize_skills
from profile_ai_extraction.schemas import StructuredProfile
from profile_analysis.benchmark import (
    BENCHMARK_NOTES,
    BENCHMARK_VERSION,
    CAREER_READINESS_SIGNALS,
    DIMENSION_WEIGHTS,
    GRADE_THRESHOLDS,
    ROLE_BENCHMARKS,
    SCORING_VERSION,
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


@dataclass(frozen=True)
class RoleResolution:
    slug: str | None
    benchmark: dict | None
    label: str | None
    source: str
    confidence: float


IDENTITY_HEADINGS = {
    "curriculum vitae", "resume", "profile", "summary", "objective", "contact",
    "experience", "education", "skills", "projects", "hồ sơ", "kinh nghiệm",
    "học vấn", "kỹ năng", "mục tiêu nghề nghiệp",
}


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def analysis_benchmark_is_fresh(analysis: dict) -> bool:
    if analysis.get("benchmark_type") != "dynamic_market":
        return True
    expires_at = (analysis.get("benchmark_snapshot") or {}).get("expires_at")
    if not expires_at:
        return False
    try:
        parsed = datetime.datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    if not parsed.tzinfo:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return parsed > datetime.datetime.now(datetime.timezone.utc)


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


def log_analysis_event(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=True, default=str))


def extract_matching_skills(text: str, aliases_by_skill: dict[str, list[str]] | None = None) -> list[str]:
    normalized = normalize_text(text)
    matches = []
    catalog = aliases_by_skill or SKILL_ALIASES
    for skill, aliases in catalog.items():
        if contains_any(normalized, aliases):
            matches.append(skill)
    return sorted(matches)


def extract_role_heading(text: str, max_lines: int = 16, max_chars: int = 1200) -> str:
    """Keep role inference inside the CV header/profile area, away from body keywords."""
    section_boundaries = {
        "education", "employment history", "experience", "work experience",
        "projects", "project experience", "skills", "technical skills",
        "certifications", "awards",
    }
    selected = []
    size = 0
    for line in split_lines(text)[:max_lines]:
        if selected and normalize_text(line).strip(" :|-") in section_boundaries:
            break
        if size + len(line) > max_chars:
            break
        selected.append(line)
        size += len(line) + 1
    return "\n".join(selected)


def matches_role_alias(context: str, alias: str, *, strict_heading: bool = False) -> bool:
    normalized_alias = normalize_text(alias).strip()
    if not normalized_alias:
        return False
    if not strict_heading:
        return contains_any(context, [normalized_alias])

    if len(normalized_alias.split()) > 1:
        return contains_any(context, [normalized_alias])

    role_suffixes = (
        "engineer", "developer", "analyst", "scientist", "designer", "specialist",
        "consultant", "manager",
    )
    for line in context.splitlines():
        normalized_line = normalize_text(line).strip(" :|-")
        if normalized_line == normalized_alias:
            return True
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?:[- /]+)({'|'.join(role_suffixes)})(?![a-z0-9])"
        if re.search(pattern, normalized_line):
            return True
    return False


def resolve_target_role(
    text: str,
    target_role: str | None = None,
    message: str | None = None,
    role_hint: str | None = None,
) -> RoleResolution:
    contexts = [
        ("user_target", normalize_text(target_role or ""), 1.0, False),
        ("user_message", normalize_text(message or ""), 0.95, False),
        ("ai_cv_hint", normalize_text(role_hint or ""), 0.85, False),
        ("cv_heading", normalize_text(extract_role_heading(text)), 0.75, True),
    ]
    candidates = []
    for slug, benchmark in ROLE_BENCHMARKS.items():
        for source, context, confidence, strict_heading in contexts:
            if not context:
                continue
            matched_aliases = [
                alias for alias in benchmark["aliases"]
                if matches_role_alias(context, alias, strict_heading=strict_heading)
            ]
            if matched_aliases:
                longest_alias = max(len(normalize_text(alias)) for alias in matched_aliases)
                candidates.append((confidence, longest_alias, slug, benchmark, source))
                break

    if not candidates:
        return RoleResolution(None, None, target_role or role_hint or None, "unresolved", 0.0)

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    confidence, _, slug, benchmark, source = candidates[0]
    return RoleResolution(slug, benchmark, benchmark["label"], source, confidence)


def detect_target_role(
    text: str,
    target_role: str | None = None,
    message: str | None = None,
) -> tuple[str | None, dict | None]:
    resolution = resolve_target_role(text, target_role=target_role, message=message)
    return resolution.slug, resolution.benchmark


def extract_candidate_identity(
    text: str,
    structured_profile: StructuredProfile | None,
) -> dict[str, str]:
    email_match = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text)
    phone_match = re.search(r"(?:\+?\d[\d .()-]{7,}\d)", text)

    full_name = structured_profile.full_name.strip() if structured_profile else ""
    if not full_name:
        for line in split_lines(text)[:10]:
            normalized = normalize_text(line).strip(":")
            words = line.split()
            if (
                normalized not in IDENTITY_HEADINGS
                and 2 <= len(words) <= 6
                and len(line) <= 60
                and "@" not in line
                and not any(char.isdigit() for char in line)
                and all(any(char.isalpha() for char in word) for word in words)
            ):
                full_name = line.strip()
                break

    return {
        "full_name": full_name,
        "email": (
            structured_profile.email.strip().lower()
            if structured_profile and structured_profile.email.strip()
            else (email_match.group(0).lower() if email_match else "")
        ),
        "phone": (
            structured_profile.phone.strip()
            if structured_profile and structured_profile.phone.strip()
            else (phone_match.group(0).strip() if phone_match else "")
        ),
        "location": structured_profile.location.strip() if structured_profile else "",
        "linkedin_url": structured_profile.linkedin_url.strip() if structured_profile else "",
        "github_url": structured_profile.github_url.strip() if structured_profile else "",
        "portfolio_url": structured_profile.portfolio_url.strip() if structured_profile else "",
    }


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


def skill_evidence_level(
    skill: str,
    skills: list[str],
    text: str = "",
    work_lines: list[str] | None = None,
    project_lines: list[str] | None = None,
    aliases_by_skill: dict[str, list[str]] | None = None,
) -> float:
    aliases = list((aliases_by_skill or SKILL_ALIASES).get(skill, [skill]))
    aliases = unique_keep_order([skill, *aliases])
    normalized_skill_keys = {
        normalize_key(display_name(candidate))
        for candidate in skills
        if normalize_key(candidate)
    }
    benchmark_keys = {
        normalize_key(display_name(candidate))
        for candidate in aliases
        if normalize_key(candidate)
    }
    mentioned_in_text = bool(text and contains_any(normalize_text(text), aliases))
    if not normalized_skill_keys.intersection(benchmark_keys) and not mentioned_in_text:
        return 0.0
    level = 0.25
    for line in project_lines or []:
        if contains_any(normalize_text(line), aliases):
            level = max(level, 0.60)
            if count_quantified_achievements(line):
                level = 1.0
    for line in work_lines or []:
        if contains_any(normalize_text(line), aliases):
            level = max(level, 0.80)
            if count_quantified_achievements(line):
                level = 1.0
    if mentioned_in_text and level == 0.25:
        level = 0.35
    return level


def score_role_skill_fit(
    skills: list[str],
    benchmark: dict,
    text: str = "",
    work_lines: list[str] | None = None,
    project_lines: list[str] | None = None,
) -> ScoreDimension:
    core_skills = benchmark["core_skills"]
    essential_groups = benchmark.get("essential_skill_groups") or [[skill] for skill in core_skills]
    supporting_skills = benchmark["supporting_skills"]
    aliases_by_skill = benchmark.get("skill_aliases") or SKILL_ALIASES
    evidence_levels = {
        skill: skill_evidence_level(
            skill,
            skills,
            text,
            work_lines,
            project_lines,
            aliases_by_skill,
        )
        for skill in set(core_skills + supporting_skills)
    }
    dynamic_weights = benchmark.get("skill_weights") or {}
    if dynamic_weights:
        essential_weights = {
            skill: float(dynamic_weights.get(skill, 0.0))
            for skill in core_skills
            if float(dynamic_weights.get(skill, 0.0)) > 0
        }
        supporting_weights = {
            skill: float(dynamic_weights.get(skill, 0.0))
            for skill in supporting_skills
            if float(dynamic_weights.get(skill, 0.0)) > 0
        }
        essential_weight_total = sum(essential_weights.values()) or 1.0
        essential_coverage = sum(
            evidence_levels.get(skill, 0.0) * weight
            for skill, weight in essential_weights.items()
        ) / essential_weight_total

        supporting_target_count = max(
            1,
            int(benchmark.get("supporting_target_count") or min(4, len(supporting_weights) or 1)),
        )
        supporting_capacity = sum(
            sorted(supporting_weights.values(), reverse=True)[:supporting_target_count]
        ) or 1.0
        supporting_coverage = min(
            1.0,
            sum(
                evidence_levels.get(skill, 0.0) * weight
                for skill, weight in supporting_weights.items()
            ) / supporting_capacity,
        )
        if essential_weights and supporting_weights:
            essential_share, supporting_share = 0.65, 0.35
        elif essential_weights:
            essential_share, supporting_share = 1.0, 0.0
        else:
            essential_share, supporting_share = 0.0, 1.0
        score = min(
            100,
            essential_coverage * essential_share * 100
            + supporting_coverage * supporting_share * 100,
        )
        matched = [skill for skill in dynamic_weights if evidence_levels.get(skill, 0.0) > 0]
        missing = [skill for skill in core_skills if evidence_levels.get(skill, 0.0) == 0]
        return ScoreDimension(
            key="role_skill_fit",
            label="Role skill fit",
            score=round(score, 2),
            weight=DIMENSION_WEIGHTS["role_skill_fit"],
            evidence=[
                f"{skill}: evidence {evidence_levels[skill]:.2f}, market weight {dynamic_weights[skill]:.3f}"
                for skill in matched
            ] + [
                f"Essential coverage: {essential_coverage:.2f}",
                f"Supporting specialization coverage: {supporting_coverage:.2f}",
            ],
            missing=missing,
        )
    group_levels = [max(evidence_levels[skill] for skill in group) for group in essential_groups]
    matched_core = [skill for skill in core_skills if evidence_levels[skill] > 0]
    matched_supporting = [skill for skill in supporting_skills if evidence_levels[skill] > 0]
    core_score = sum(group_levels) / max(len(essential_groups), 1) * 75
    supporting_score = (
        sum(evidence_levels[skill] for skill in supporting_skills)
        / max(len(supporting_skills), 1)
        * 25
    )
    score = min(100, core_score + supporting_score)
    missing = [
        "one of: " + ", ".join(group) if len(group) > 1 else group[0]
        for group in essential_groups
        if not any(evidence_levels[skill] > 0 for skill in group)
    ]

    return ScoreDimension(
        key="role_skill_fit",
        label="Role skill fit",
        score=round(score, 2),
        weight=DIMENSION_WEIGHTS["role_skill_fit"],
        evidence=[
            f"{skill}: evidence {evidence_levels[skill]:.2f}"
            for skill in matched_core + matched_supporting
        ],
        missing=missing,
    )


def score_experience_evidence(
    text: str,
    work_lines: list[str],
    project_lines: list[str],
    structured_profile: StructuredProfile | None = None,
) -> ScoreDimension:
    normalized = normalize_text(text)
    action_hits = [verb for verb in ACTION_VERBS if normalize_text(verb) in normalized]
    quantified_count = count_quantified_achievements(text)
    if structured_profile:
        work_record_count = len(structured_profile.work_experiences)
        impact_evidence_count = sum(
            len(item.impact_evidence)
            for item in [*structured_profile.work_experiences, *structured_profile.projects]
        )
    else:
        work_record_count = min(3, max(1, len(work_lines) // 2)) if work_lines else 0
        impact_evidence_count = 0

    delivery_signal_groups = {
        "stakeholder delivery": ["customer", "client", "stakeholder", "onsite", "business-facing"],
        "deployment": [
            "deployed", "deployment", "production", "cloud run", "ci/cd",
            "release", "migration", "operations", "maintenance",
        ],
        "quality": ["testing", "unit test", "validation", "quality", "monitoring"],
        "security": ["permission", "access control", "secure", "authorization"],
        "documentation": ["documentation", "documented", "source-to-target", "tool contract"],
    }
    delivery_signals = [
        label
        for label, keywords in delivery_signal_groups.items()
        if contains_any(normalized, keywords)
    ]

    score = 10
    if work_record_count:
        score += 10 + min(work_record_count, 3) * 4
    if project_lines:
        score += 5 + min(len(project_lines), 2) * 4
    score += min(len(action_hits), 5) * 3
    score += min(quantified_count, 5) * 5
    score += min(len(delivery_signals), 5) * 3
    score += min(impact_evidence_count, 5) * 2
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
    if delivery_signals:
        evidence.append(f"Delivery signals: {', '.join(delivery_signals)}")
    if impact_evidence_count:
        evidence.append(f"{impact_evidence_count} structured impact statements")

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


def score_cv_clarity(
    text: str,
    skills: list[str],
    structured_profile: StructuredProfile | None = None,
) -> ScoreDimension:
    normalized = normalize_text(text)
    lines = split_lines(text)
    evidence = []
    score = 25

    if re.search(r"[\w.+-]+@[\w-]+\.[\w.-]+", text) or (
        structured_profile and structured_profile.email
    ):
        score += 12
        evidence.append("email")
    if "linkedin" in normalized or (
        structured_profile and structured_profile.linkedin_url
    ):
        score += 10
        evidence.append("linkedin")
    if "github" in normalized or "portfolio" in normalized or (
        structured_profile
        and (structured_profile.github_url or structured_profile.portfolio_url)
    ):
        score += 10
        evidence.append("portfolio/github")
    section_hits = [
        section
        for section, keywords in SECTION_PATTERNS.items()
        if contains_any(normalized, keywords)
    ]
    if structured_profile:
        structured_sections = {
            "experience": bool(structured_profile.work_experiences),
            "education": bool(structured_profile.education),
            "projects": bool(structured_profile.projects),
            "skills": bool(structured_profile.skills),
        }
        section_hits = unique_keep_order(
            section_hits
            + [
                section
                for section, present in structured_sections.items()
                if present
            ]
        )
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
            ", ".join(item.skills[:8]),
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
    certifications = [
        f"certification: {item}"
        for item in structured_profile.certifications
    ]
    achievements = [
        f"achievement: {item}"
        for item in structured_profile.achievements
    ]
    return " ".join(
        structured_profile.career_readiness_signals
        + certifications
        + achievements
    )


def build_message(
    grade: str | None,
    score: float | None,
    benchmark_label: str | None,
    benchmark_status: str = "resolved",
) -> str:
    if benchmark_status in {"insufficient_market_evidence", "benchmark_unavailable"} and benchmark_label:
        return (
            f"Profile Scanner đã trích xuất CV cho vị trí {benchmark_label}, nhưng dữ liệu thị trường theo role này "
            "chưa đạt ngưỡng bằng chứng để xếp hạng. Hệ thống không tự ép CV sang một role khác."
        )
    if not grade or score is None or not benchmark_label:
        return (
            "Profile Scanner đã trích xuất hồ sơ nhưng chưa xác định được target role thuộc bộ benchmark đang hỗ trợ. "
            "Hãy cho biết vị trí mục tiêu cụ thể để hệ thống chấm điểm mà không ép CV vào một ngành gần nhất."
        )
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


def build_benchmark_snapshot(
    *,
    benchmark: dict | None,
    role_resolution: RoleResolution,
    benchmark_type: str,
    dynamic_snapshot: DynamicBenchmarkSnapshot | None,
    static_benchmark: dict | None,
) -> dict | None:
    if not benchmark:
        return None
    if benchmark_type == "dynamic_market" and dynamic_snapshot:
        payload = dynamic_snapshot.model_dump(mode="json")
        payload.update({
            "benchmark_type": benchmark_type,
            "scoring_criteria": benchmark,
            "riasec": (static_benchmark or {}).get("riasec"),
            "riasec_source": (
                "static_role_taxonomy"
                if (static_benchmark or {}).get("riasec")
                else None
            ),
        })
        return payload
    return {
        "benchmark_id": role_resolution.slug,
        "benchmark_type": benchmark_type,
        "normalized_role": role_resolution.label,
        "level": benchmark.get("level"),
        "status": "ready",
        "compiler_version": BENCHMARK_VERSION,
        "scoring_criteria": benchmark,
        "riasec": benchmark.get("riasec"),
        "riasec_source": "static_role_taxonomy" if benchmark.get("riasec") else None,
    }


def infer_candidate_benchmark_level(
    role_query: str,
    structured_profile: StructuredProfile | None,
    parsed_text: str,
) -> str:
    """Resolve a market cohort without allowing body keywords to override an explicit target."""
    explicit_level = infer_level(role_query)
    if explicit_level != "unspecified":
        return explicit_level

    titles = [
        item.title
        for item in (structured_profile.work_experiences if structured_profile else [])
        if item.title
    ]
    title_text = normalize_text(" | ".join(titles))
    if contains_any(title_text, ["manager", "head", "director"]):
        return "senior"
    if contains_any(title_text, ["senior", "principal", "architect"]) or re.search(
        r"\b(?:(?:tech|team|engineering)\s+lead|lead\s+(?:engineer|developer|scientist))\b",
        title_text,
    ):
        return "senior"

    profile_text = compact_parts([
        structured_profile.headline if structured_profile else "",
        structured_profile.summary if structured_profile else "",
        " | ".join(titles),
        " | ".join(
            compact_parts([
                item.degree,
                item.field,
                item.duration,
                item.evidence,
            ])
            for item in (structured_profile.education if structured_profile else [])
        ),
        extract_role_heading(parsed_text),
    ])
    normalized_profile = normalize_text(profile_text)
    if contains_any(
        normalized_profile,
        ["intern", "internship", "fresher", "junior", "student", "undergraduate", "graduate"],
    ):
        return "entry"

    years = [
        float(match)
        for match in re.findall(r"\b(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)\b", normalized_profile)
    ]
    if years and max(years) >= 5:
        return "senior"
    if years and max(years) <= 2:
        return "entry"
    return "unspecified"


async def analyze_cv_profile(document: dict) -> ProfileAnalysisResult:
    skill_normalization_version = "skill-normalization-v3"
    existing = document.get("profile_analysis")
    can_reuse_existing = (
        existing
        and document.get("analysis_status") == "completed"
        and existing.get("benchmark_version") in {BENCHMARK_VERSION, DYNAMIC_BENCHMARK_VERSION}
        and existing.get("scoring_version") == SCORING_VERSION
        and existing.get("skill_normalization_version") == skill_normalization_version
        and analysis_benchmark_is_fresh(existing)
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

    log_analysis_event(
        "cv_profile_analysis_started",
        cv_document_id=cv_document_id,
        parser_type=document.get("parser_type"),
        text_char_count=len(parsed_text),
        requested_target_role_present=bool(document.get("requested_target_role")),
    )
    structured_profile = await asyncio.to_thread(
        extract_structured_profile_with_ai,
        parsed_text=parsed_text,
        target_role=document.get("requested_target_role"),
        message=document.get("message"),
    )

    raw_skills = unique_keep_order(extract_matching_skills(parsed_text) + skills_from_ai(structured_profile))
    normalized_skills = normalize_skills(raw_skills, parsed_text)
    skills = [skill["canonical_name"] for skill in normalized_skills]
    role_resolution = resolve_target_role(
        parsed_text,
        target_role=document.get("requested_target_role"),
        message=document.get("message"),
        role_hint=structured_profile.target_role_hint if structured_profile else None,
    )
    ai_work_lines, ai_education_lines, ai_project_lines, ai_achievement_lines = profile_lines_from_ai(structured_profile)
    work_lines = unique_keep_order(ai_work_lines + extract_work_experience_lines(parsed_text), 8)
    project_lines = unique_keep_order(ai_project_lines + extract_project_lines(parsed_text), 8)
    education_lines = unique_keep_order(ai_education_lines + extract_education_lines(parsed_text), 6)
    scoring_text = compact_parts([
        parsed_text,
        "\n".join(ai_work_lines),
        "\n".join(ai_project_lines),
        "\n".join(ai_education_lines),
        career_readiness_text_from_ai(structured_profile),
        "\n".join(ai_achievement_lines),
    ])
    log_analysis_event(
        "cv_profile_extraction_completed",
        cv_document_id=cv_document_id,
        ai_extraction_used=structured_profile is not None,
        ai_extraction_confidence=structured_profile.confidence if structured_profile else None,
        raw_skill_count=len(raw_skills),
        normalized_skill_count=len(normalized_skills),
        normalized_skill_ids=[skill["skill_id"] for skill in normalized_skills],
        work_evidence_count=len(work_lines),
        education_evidence_count=len(education_lines),
        project_evidence_count=len(project_lines),
    )
    log_analysis_event(
        "cv_target_role_resolved",
        cv_document_id=cv_document_id,
        role_slug=role_resolution.slug,
        role_label=role_resolution.label,
        source=role_resolution.source,
        confidence=role_resolution.confidence,
    )

    benchmark = role_resolution.benchmark
    static_benchmark = benchmark
    dynamic_snapshot: DynamicBenchmarkSnapshot | None = None
    benchmark_status = "resolved" if benchmark else "needs_target_role"
    benchmark_type = "static" if benchmark else "none"
    role_query = (document.get("requested_target_role") or role_resolution.label or "").strip()
    if settings.dynamic_benchmark_enabled and role_query:
        try:
            candidate_level = infer_candidate_benchmark_level(
                role_query,
                structured_profile,
                parsed_text,
            )
            dynamic_snapshot = await asyncio.to_thread(
                compile_dynamic_benchmark,
                role_query=role_query,
                location_id=settings.benchmark_default_location,
                level=candidate_level,
            )
            if dynamic_snapshot.status == "ready":
                benchmark = dynamic_snapshot.as_scoring_benchmark()
                role_resolution = RoleResolution(
                    dynamic_snapshot.benchmark_id,
                    benchmark,
                    dynamic_snapshot.normalized_role,
                    "market_benchmark",
                    dynamic_snapshot.confidence_score,
                )
                benchmark_status = "market_resolved"
                benchmark_type = "dynamic_market"
            elif benchmark:
                benchmark_status = "fallback_static"
                benchmark_type = "static_fallback"
            else:
                role_resolution = RoleResolution(None, None, role_query, "user_target", 1.0)
                benchmark_status = "insufficient_market_evidence"
                benchmark_type = "dynamic_market"
        except Exception as exc:
            logger.exception(
                "Dynamic benchmark compilation failed",
                extra={"error_type": type(exc).__name__, "target_role": role_query},
            )
            benchmark_status = "fallback_static" if benchmark else "benchmark_unavailable"
            benchmark_type = "static_fallback" if benchmark else "none"

    log_analysis_event(
        "cv_benchmark_selected",
        cv_document_id=cv_document_id,
        benchmark_type=benchmark_type,
        benchmark_status=benchmark_status,
        benchmark_profile_id=(
            dynamic_snapshot.benchmark_id
            if dynamic_snapshot and dynamic_snapshot.status == "ready"
            else role_resolution.slug
        ),
        cohort_size=dynamic_snapshot.cohort_size if dynamic_snapshot else None,
        distinct_company_count=dynamic_snapshot.distinct_company_count if dynamic_snapshot else None,
        confidence=dynamic_snapshot.confidence if dynamic_snapshot else None,
        level=dynamic_snapshot.level if dynamic_snapshot else None,
    )
    if benchmark and benchmark.get("skill_aliases"):
        raw_skills = unique_keep_order(
            raw_skills
            + extract_matching_skills(parsed_text, benchmark["skill_aliases"])
            + skills_from_ai(structured_profile)
        )
        normalized_skills = normalize_skills(
            raw_skills,
            parsed_text,
            priority_skills=[
                *benchmark.get("core_skills", []),
                *benchmark.get("supporting_skills", []),
            ],
        )
        skills = [skill["canonical_name"] for skill in normalized_skills]
    benchmark_snapshot = build_benchmark_snapshot(
        benchmark=benchmark,
        role_resolution=role_resolution,
        benchmark_type=benchmark_type,
        dynamic_snapshot=dynamic_snapshot,
        static_benchmark=static_benchmark,
    )
    dimensions = []
    total_score = None
    grade = None
    if benchmark:
        dimensions = [
            score_role_skill_fit(skills, benchmark, scoring_text, work_lines, project_lines),
            score_experience_evidence(
                scoring_text,
                work_lines,
                project_lines,
                structured_profile,
            ),
            score_education_certification(scoring_text, education_lines, benchmark),
            score_career_readiness(scoring_text),
            score_cv_clarity(parsed_text, skills, structured_profile),
        ]
        total_score = compute_total_score(dimensions)
        grade = grade_from_score(total_score)
    log_analysis_event(
        "cv_scoring_completed",
        cv_document_id=cv_document_id,
        target_role=role_resolution.label,
        scoring_version=SCORING_VERSION,
        grade=grade,
        total_score=total_score,
        dimensions={
            dimension.key: {
                "score": dimension.score,
                "weight": dimension.weight,
                "evidence_count": len(dimension.evidence),
                "missing_count": len(dimension.missing),
            }
            for dimension in dimensions
        },
    )
    analyzed_at = utc_now()
    candidate_identity = extract_candidate_identity(parsed_text, structured_profile)

    missing_signals = unique_keep_order(
        [missing for dimension in dimensions for missing in dimension.missing],
        10,
    )
    result = ProfileAnalysisResult(
        cv_document_id=cv_document_id,
        target_role=role_resolution.label,
        target_role_source=role_resolution.source,
        target_role_confidence=role_resolution.confidence,
        benchmark_status=benchmark_status,
        benchmark_profile_id=(
            dynamic_snapshot.benchmark_id
            if benchmark_type == "dynamic_market" and dynamic_snapshot
            else role_resolution.slug
        ),
        benchmark_version=(
            dynamic_snapshot.compiler_version
            if benchmark_type == "dynamic_market" and dynamic_snapshot
            else BENCHMARK_VERSION
        ),
        scoring_version=SCORING_VERSION,
        benchmark_type=benchmark_type,
        benchmark_confidence=dynamic_snapshot.confidence if dynamic_snapshot else None,
        benchmark_confidence_score=dynamic_snapshot.confidence_score if dynamic_snapshot else None,
        benchmark_sample_size=dynamic_snapshot.cohort_size if dynamic_snapshot else None,
        benchmark_distinct_companies=dynamic_snapshot.distinct_company_count if dynamic_snapshot else None,
        benchmark_sources=dynamic_snapshot.evidence_sources if dynamic_snapshot else [],
        benchmark_snapshot=benchmark_snapshot,
        grade=grade,
        total_score=total_score,
        score_dimensions=dimensions,
        extracted_skills=skills,
        normalized_skills=normalized_skills,
        raw_extracted_skills=raw_skills,
        skill_normalization_version=skill_normalization_version,
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
        recommendations=(
            build_recommendations(dimensions)
            if benchmark
            else (
                ["Benchmark thị trường hiện chưa đủ bằng chứng để xếp hạng CV cho role này."]
                if role_query
                else ["Cung cấp target role cụ thể để áp dụng đúng benchmark nghề nghiệp."]
            )
        ),
        benchmark_notes=(
            (DYNAMIC_BENCHMARK_NOTES if benchmark_type == "dynamic_market" else BENCHMARK_NOTES)
            + ([
                f"Dynamic market benchmark uses {dynamic_snapshot.cohort_size} role-matched jobs from a {dynamic_snapshot.window_days}-day window."
            ] if dynamic_snapshot else [])
            + (dynamic_snapshot.limitations if dynamic_snapshot else [])
        ),
        ai_extraction_used=structured_profile is not None,
        ai_extraction_confidence=structured_profile.confidence if structured_profile else None,
        structured_profile=structured_profile.as_firestore_payload() if structured_profile else None,
        candidate_identity=candidate_identity,
        analyzed_at=analyzed_at,
        message_vi=build_message(grade, total_score, role_resolution.label, benchmark_status),
    )

    analysis_object = build_artifact_object_name(original_object, "profile_analysis.json")
    analysis_uri = f"gs://{bucket.name}/{analysis_object}"
    result.analysis_artifact_gcs_uri = analysis_uri
    upload_json_artifact(bucket, analysis_object, result.as_artifact_payload())

    await update_cv_document(cv_document_id, {
        "analysis_status": "completed",
        "profile_analysis": result.as_firestore_payload(),
        "analysis_object": analysis_object,
        "analysis_gcs_uri": analysis_uri,
        "grade": grade,
        "total_score": total_score,
        "target_role": result.target_role,
        "target_role_source": role_resolution.source,
        "target_role_confidence": role_resolution.confidence,
        "benchmark_status": result.benchmark_status,
        "benchmark_profile_id": result.benchmark_profile_id,
        "benchmark_version": result.benchmark_version,
        "scoring_version": result.scoring_version,
        "benchmark_type": result.benchmark_type,
        "analyzed_at": analyzed_at,
        "next_status": "analysis_completed",
    })

    return result
