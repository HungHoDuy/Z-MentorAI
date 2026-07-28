import re
import unicodedata


ALIASES = {
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "gcp": "Google Cloud Platform",
    "google cloud": "Google Cloud Platform",
    "google cloud platform": "Google Cloud Platform",
    "aws": "Amazon Web Services",
    "rest api": "REST API",
    "restful api": "REST API",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "reactjs": "React",
    "react.js": "React",
    "c sharp": "C#",
    "c#": "C#",
    "ci/cd": "CI/CD",
    "ci cd": "CI/CD",
    "t sql": "T-SQL",
    "nl to sql": "NL-to-SQL",
    "computer vision": "Computer Vision",
    "deep learning": "Deep Learning",
    "retrieval augmented generation": "Retrieval-Augmented Generation",
    "langchain": "LangChain",
    "llamaindex": "LlamaIndex",
    "opencv": "OpenCV",
    "scikit learn": "scikit-learn",
    "spring boot": "Spring Boot",
    ".net": ".NET",
    "asp.net": "ASP.NET",
}

TOO_GENERIC = {
    "api", "cloud", "coding", "computer", "data", "database", "development",
    "framework", "programming", "software", "technology", "web",
}

NON_SKILL_PHRASES = {
    "clear technical explanation", "onsite collaboration", "onsite communication",
    "technical understanding", "business understanding", "strong knowledge",
    "good knowledge", "responsibility", "responsibilities", "working experience",
}

SOFT_SKILLS = {
    "communication", "teamwork", "leadership", "critical thinking",
    "problem solving", "time management", "adaptability",
}

CATEGORIES = {
    "JavaScript": "programming_language",
    "TypeScript": "programming_language",
    "Python": "programming_language",
    "Java": "programming_language",
    "C#": "programming_language",
    "Machine Learning": "ai_data",
    "Artificial Intelligence": "ai_data",
    "Computer Vision": "ai_data",
    "Deep Learning": "ai_data",
    "PyTorch": "ai_framework",
    "TensorFlow": "ai_framework",
    "LangChain": "ai_framework",
    "LlamaIndex": "ai_framework",
    "OpenCV": "ai_framework",
    "Retrieval-Augmented Generation": "ai_data",
    "Google Cloud Platform": "cloud_platform",
    "Amazon Web Services": "cloud_platform",
    "PostgreSQL": "database",
    "REST API": "backend_api",
    "Node.js": "framework_runtime",
    "React": "framework_runtime",
}


def normalize_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").strip()
    value = re.sub(r"^[^\w#+.]+|[^\w#+.]+$", "", value)
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())


def display_name(value: str) -> str:
    key = normalize_key(value)
    if key in ALIASES:
        return ALIASES[key]
    acronyms = {
        "sql": "SQL", "html": "HTML", "css": "CSS", "nlp": "NLP", "llm": "LLM",
        "fastapi": "FastAPI", "numpy": "NumPy", "pandas": "Pandas", "pytorch": "PyTorch",
        "tensorflow": "TensorFlow", "mongodb": "MongoDB", "mysql": "MySQL", "graphql": "GraphQL",
        "docker": "Docker", "kubernetes": "Kubernetes", "git": "Git",
    }
    if key in acronyms:
        return acronyms[key]
    return " ".join(part.capitalize() for part in key.split())


def normalize_skills(
    raw_skills: list[str],
    cv_text: str,
    limit: int = 30,
    priority_skills: list[str] | None = None,
) -> list[dict]:
    """Canonicalize names, deduplicate aliases, and reject ungrounded LLM output."""
    evidence_text = normalize_key(cv_text)
    priority_keys = {normalize_key(display_name(skill)) for skill in priority_skills or []}
    candidates: dict[str, dict] = {}
    for source_order, raw in enumerate(raw_skills):
        key = normalize_key(str(raw))
        if (
            not key
            or len(key) > 60
            or len(key.split()) > 5
            or key in TOO_GENERIC
            or key in NON_SKILL_PHRASES
        ):
            continue
        canonical = display_name(key)
        canonical_key = normalize_key(canonical)
        aliases = {key, canonical_key}
        evidence_count = sum(
            len(re.findall(rf"(?<!\w){re.escape(alias)}(?!\w)", evidence_text))
            for alias in aliases
            if alias
        )
        if evidence_count <= 0:
            continue
        is_soft_skill = canonical_key in SOFT_SKILLS
        relevance_score = (
            min(evidence_count, 5) * 2
            + (6 if canonical_key in priority_keys else 0)
            + (0 if is_soft_skill else 2)
        )
        candidate = {
            "skill_id": re.sub(r"[^a-z0-9]+", "-", canonical_key).strip("-"),
            "canonical_name": canonical,
            "display_name_vi": canonical,
            "display_name_en": canonical,
            "category": "soft_skill" if is_soft_skill else CATEGORIES.get(canonical, "technical_skill"),
            "is_soft_skill": is_soft_skill,
            "evidence_status": "explicit",
            "evidence_count": evidence_count,
            "relevance_score": relevance_score,
            "_source_order": source_order,
        }
        previous = candidates.get(canonical_key)
        if not previous or candidate["relevance_score"] > previous["relevance_score"]:
            candidates[canonical_key] = candidate
    ranked = sorted(
        candidates.values(),
        key=lambda item: (
            -item["relevance_score"],
            item["is_soft_skill"],
            item["_source_order"],
            item["canonical_name"].casefold(),
        ),
    )[:limit]
    for item in ranked:
        item.pop("_source_order", None)
    return ranked
