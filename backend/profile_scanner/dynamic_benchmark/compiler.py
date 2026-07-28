from __future__ import annotations

import datetime
import hashlib
import json
import re
import unicodedata
import uuid
from functools import lru_cache
from typing import Any, Callable

from core.config import logger, settings
from dynamic_benchmark.repository import DynamicBenchmarkRepository
from dynamic_benchmark.schemas import DynamicBenchmarkSnapshot, DynamicSkillCriterion, MarketJobEvidence
from profile_ai_extraction.service import parse_json_object
from profile_analysis.benchmark import SKILL_ALIASES
from skill_normalization.service import display_name, normalize_key


DYNAMIC_BENCHMARK_VERSION = "market-benchmark-v1.2"
DYNAMIC_BENCHMARK_NOTES = [
    "Role candidates are retrieved from versioned internal job facts with multilingual vector similarity.",
    "Gemini proposes a skill vocabulary, but deterministic code counts job frequency and calculates weights.",
    "Role-skill fit combines market-weighted essential coverage with the candidate's strongest supporting specialization; alternate AI tracks are not all treated as mandatory.",
    "Every benchmark stores its evidence window, sample size, company count, source names, and representative job links.",
    "The S-E grade measures CV evidence readiness for one target role; it is not a hiring decision or personal-worth score.",
]


def infer_level(role_query: str) -> str:
    normalized = normalize(role_query)
    if re.search(r"\b(manager|director|department head|head of)\b", normalized):
        return "manager"
    if re.search(
        r"\b(senior|principal|architect|tech lead|team lead|lead engineer|lead developer|lead scientist)\b",
        normalized,
    ):
        return "senior"
    if re.search(r"\b(intern|internship|fresher|junior|entry level|graduate)\b", normalized):
        return "entry"
    return "unspecified"


def normalize_role_label(role_query: str) -> str:
    value = " ".join(role_query.split()).strip()
    return value[:120]


def benchmark_cache_key(role_query: str, level: str, location_id: str, window_days: int) -> str:
    raw = "|".join((DYNAMIC_BENCHMARK_VERSION, normalize(role_query), level, location_id, str(window_days)))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compile_dynamic_benchmark(
    *,
    role_query: str,
    location_id: str = "vietnam",
    level: str | None = None,
    force_refresh: bool = False,
    repository: DynamicBenchmarkRepository | None = None,
    vocabulary_extractor: Callable[[str, list[MarketJobEvidence]], dict[str, Any]] | None = None,
    now: datetime.datetime | None = None,
) -> DynamicBenchmarkSnapshot:
    if not role_query.strip():
        raise ValueError("role_query is required")
    now = now or datetime.datetime.now(datetime.timezone.utc)
    level = level or infer_level(role_query)
    repository = repository or DynamicBenchmarkRepository()
    cache_key = benchmark_cache_key(role_query, level, location_id, settings.benchmark_market_window_days)
    if not force_refresh:
        cached = repository.get_cached(cache_key, now)
        if cached:
            logger.info(
                json.dumps(
                    {
                        "event": "dynamic_benchmark_cache_hit",
                        "benchmark_id": cached.benchmark_id,
                        "compiler_version": cached.compiler_version,
                        "role_query": cached.role_query,
                        "confidence": cached.confidence,
                        "cohort_size": cached.cohort_size,
                    },
                    ensure_ascii=True,
                )
            )
            return cached

    jobs = repository.search_market_jobs(
        role_query=role_query,
        location_id=location_id,
        level=level,
        now=now,
        window_days=settings.benchmark_market_window_days,
        limit=settings.benchmark_search_limit,
    )
    extractor = vocabulary_extractor or extract_vocabulary_with_ai
    vocabulary = extractor(role_query, jobs)
    criteria = build_skill_criteria(jobs, vocabulary.get("skills", []))
    companies = {normalize(job.company) for job in jobs if normalize(job.company)}
    source_names = sorted({job.source for job in jobs if job.source})
    average_match_score = sum(job.match_score for job in jobs) / len(jobs) if jobs else 0.0
    status, confidence, confidence_score, limitations = evaluate_confidence(
        cohort_size=len(jobs),
        distinct_company_count=len(companies),
        skill_count=len(criteria),
        source_count=len(source_names),
        average_match_score=average_match_score,
        vocabulary_source=str(vocabulary.get("source") or "deterministic"),
    )
    generated_at = now
    snapshot = DynamicBenchmarkSnapshot(
        benchmark_id=str(uuid.uuid4()),
        cache_key=cache_key,
        compiler_version=DYNAMIC_BENCHMARK_VERSION,
        role_query=role_query.strip(),
        normalized_role=normalize_role_label(vocabulary.get("normalized_role") or role_query),
        level=level,
        location_id=location_id,
        status=status,
        confidence=confidence,
        confidence_score=confidence_score,
        window_days=settings.benchmark_market_window_days,
        window_start=(now - datetime.timedelta(days=settings.benchmark_market_window_days)).date().isoformat(),
        window_end=now.date().isoformat(),
        cohort_size=len(jobs),
        distinct_company_count=len(companies),
        source_collections=[settings.benchmark_job_facts_collection, settings.benchmark_embedding_collection],
        source_names=source_names,
        skill_criteria=criteria,
        education_keywords=clean_terms(vocabulary.get("education_keywords", []), limit=20),
        evidence_sources=[
            {
                "job_key": job.job_key,
                "job_title": job.job_title,
                "company": job.company,
                "job_url": job.job_url,
                "source": job.source,
                "source_updated_at": job.source_updated_at,
                "match_score": job.match_score,
            }
            for job in jobs[:10]
        ],
        limitations=limitations,
        vocabulary_source=str(vocabulary.get("source") or "deterministic"),
        embedding_model=settings.benchmark_embedding_model,
        generated_at=generated_at,
        expires_at=generated_at + datetime.timedelta(days=settings.benchmark_cache_days),
    )
    repository.save(snapshot)
    logger.info(
        json.dumps(
            {
                "event": "dynamic_benchmark_compiled",
                "benchmark_id": snapshot.benchmark_id,
                "compiler_version": snapshot.compiler_version,
                "role_query": snapshot.role_query,
                "level": snapshot.level,
                "location_id": snapshot.location_id,
                "status": snapshot.status,
                "confidence": snapshot.confidence,
                "cohort_size": snapshot.cohort_size,
                "distinct_company_count": snapshot.distinct_company_count,
                "source_count": len(snapshot.source_names),
                "skill_count": len(snapshot.skill_criteria),
                "window_days": snapshot.window_days,
            },
            ensure_ascii=True,
        )
    )
    return snapshot


def extract_vocabulary_with_ai(role_query: str, jobs: list[MarketJobEvidence]) -> dict[str, Any]:
    fallback = fallback_vocabulary(role_query)
    if not settings.profile_ai_extraction_enabled or not jobs:
        return fallback
    samples = []
    size = 0
    for job in jobs[:30]:
        sample = f"TITLE: {job.job_title}\nREQUIREMENTS: {job.requirements_text}\nDESCRIPTION: {job.description_text[:1200]}"
        if size + len(sample) > 18000:
            break
        samples.append(sample)
        size += len(sample)
    prompt = {
        "task": "Propose a normalized skill vocabulary for deterministic frequency counting across these job descriptions.",
        "target_role": role_query,
        "rules": [
            "Only include concrete skills, tools, methods, languages, and domain knowledge supported by the samples.",
            "Do not assign weights or candidate scores.",
            "Aliases must be literal phrases that can be counted in job text.",
            "Return JSON only.",
        ],
        "output_schema": {
            "normalized_role": "string",
            "skills": [{"name": "string", "aliases": ["string"]}],
            "education_keywords": ["string"],
        },
        "job_samples": samples,
    }
    try:
        from google.genai.types import GenerateContentConfig

        response = get_generation_client().models.generate_content(
            model=settings.profile_ai_model_name,
            contents=json.dumps(prompt, ensure_ascii=False),
            config=GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                system_instruction="You compile evidence vocabularies from job descriptions. Return valid JSON only.",
            ),
        )
        payload = parse_json_object(response.text or "")
        skills = sanitize_skill_vocabulary(payload.get("skills", []))
        if len(skills) < 3:
            return fallback
        return {
            "normalized_role": str(payload.get("normalized_role") or role_query),
            "skills": skills,
            "education_keywords": clean_terms(payload.get("education_keywords", []), limit=20),
            "source": "ai_proposed_deterministically_counted",
        }
    except Exception as exc:
        logger.exception("Dynamic benchmark vocabulary extraction failed", extra={"error_type": type(exc).__name__})
        return fallback


@lru_cache(maxsize=1)
def get_generation_client():
    from google import genai
    from google.genai.types import HttpOptions

    return genai.Client(
        vertexai=settings.use_vertex_ai,
        project=settings.google_cloud_project if settings.use_vertex_ai else None,
        location=settings.vertex_ai_location if settings.use_vertex_ai else None,
        http_options=HttpOptions(api_version="v1"),
    )


def fallback_vocabulary(role_query: str) -> dict[str, Any]:
    return {
        "normalized_role": role_query,
        "skills": [
            {"name": skill, "aliases": aliases}
            for skill, aliases in SKILL_ALIASES.items()
        ],
        "education_keywords": [],
        "source": "deterministic_fallback",
    }


def sanitize_skill_vocabulary(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    merged: dict[str, dict[str, Any]] = {}
    for item in items[:50]:
        if not isinstance(item, dict):
            continue
        name = canonical_skill_id(item.get("name"))
        if not name:
            continue
        aliases = clean_terms(
            [
                name,
                display_name(name),
                *list(item.get("aliases") or []),
                *SKILL_ALIASES.get(name, []),
            ],
            limit=15,
        )
        if not aliases:
            continue
        existing = merged.setdefault(name, {"name": name, "aliases": []})
        existing["aliases"] = clean_terms([*existing["aliases"], *aliases], limit=15)
    return list(merged.values())


def canonical_skill_id(value: Any) -> str:
    """Map noisy AI labels onto stable benchmark skill identifiers."""
    normalized = normalize_term(value)
    if not normalized:
        return ""
    candidates: list[tuple[int, str]] = []
    for canonical, aliases in SKILL_ALIASES.items():
        for alias in [canonical, *aliases]:
            normalized_alias = normalize_term(alias)
            if not normalized_alias:
                continue
            if normalized == normalized_alias:
                if display_name(normalized) == display_name(canonical):
                    return canonical
                return normalize_key(display_name(normalized))[:80]
            if re.search(rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])", normalized):
                candidates.append((len(normalized_alias), canonical))
    if candidates:
        return max(candidates)[1]
    return normalize_key(display_name(normalized))[:80]


def build_skill_criteria(jobs: list[MarketJobEvidence], vocabulary: list[dict[str, Any]]) -> list[DynamicSkillCriterion]:
    if not jobs:
        return []
    normalized_vocabulary = sanitize_skill_vocabulary(vocabulary)
    vocabulary_names = {item["name"] for item in normalized_vocabulary}
    counted = []
    for item in normalized_vocabulary:
        aliases = [
            alias
            for alias in item["aliases"]
            if canonical_skill_id(alias) == item["name"]
            or canonical_skill_id(alias) not in vocabulary_names
        ]
        aliases = clean_terms([item["name"], *aliases], limit=15)
        count = sum(1 for job in jobs if contains_alias(job.requirements_text + "\n" + job.description_text, aliases))
        share = count / len(jobs)
        if count >= 2 and share >= settings.benchmark_min_skill_share:
            counted.append((item["name"], aliases, count, share))
    counted.sort(key=lambda item: (-item[3], -item[2], item[0]))
    counted = counted[: settings.benchmark_max_skills]
    if not counted:
        return []
    essential_ids = {
        name for name, _, _, share in counted if share >= settings.benchmark_essential_skill_share
    }
    if not essential_ids:
        essential_ids = {item[0] for item in counted[: min(5, len(counted))]}
    share_total = sum(item[3] for item in counted) or 1.0
    return [
        DynamicSkillCriterion(
            skill_id=name,
            label=name,
            aliases=aliases,
            job_count=count,
            job_share=round(share, 4),
            weight=round(share / share_total, 6),
            tier="essential" if name in essential_ids else "supporting",
        )
        for name, aliases, count, share in counted
    ]


def evaluate_confidence(
    *,
    cohort_size: int,
    distinct_company_count: int,
    skill_count: int,
    source_count: int,
    average_match_score: float,
    vocabulary_source: str,
) -> tuple[str, str, float, list[str]]:
    limitations = [
        "Market evidence currently comes from available internal job-posting sources.",
        f"Evidence window is capped at {settings.benchmark_market_window_days} days.",
    ]
    if (
        cohort_size >= 30
        and distinct_company_count >= 5
        and skill_count >= 5
        and source_count >= 2
        and average_match_score >= 0.70
    ):
        score = 0.9 if vocabulary_source.startswith("ai_") else 0.8
        return "ready", "high", score, limitations
    if cohort_size >= 10 and distinct_company_count >= 3 and skill_count >= 3:
        if source_count < 2:
            limitations.append("Only one independent job-posting source is available; confidence is capped at medium.")
        if average_match_score < 0.70:
            limitations.append("Average semantic role-match confidence is below the high-confidence threshold.")
        limitations.append("The role cohort is usable but below the high-confidence sample threshold.")
        score = 0.7 if vocabulary_source.startswith("ai_") else 0.6
        return "ready", "medium", score, limitations
    limitations.append("Insufficient role-specific jobs, companies, or repeatable skill signals for grading.")
    return "insufficient_evidence", "low", 0.3, limitations


def contains_alias(text: str, aliases: list[str]) -> bool:
    normalized = normalize(text)
    for alias in aliases:
        term = normalize(alias)
        if not term:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", normalized):
            return True
    return False


def normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = re.sub(r"[^a-zA-Z0-9+#.]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def normalize_term(value: Any) -> str:
    return normalize(value)[:80]


def clean_terms(values: Any, limit: int) -> list[str]:
    if not isinstance(values, (list, tuple, set)):
        return []
    result = []
    seen = set()
    for value in values:
        term = normalize_term(value)
        if len(term) < 2 or term in seen:
            continue
        seen.add(term)
        result.append(term)
        if len(result) >= limit:
            break
    return result
