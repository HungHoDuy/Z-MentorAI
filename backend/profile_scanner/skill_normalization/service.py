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
}

TOO_GENERIC = {
    "api", "cloud", "coding", "computer", "data", "database", "development",
    "framework", "programming", "software", "technology", "web",
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


def normalize_skills(raw_skills: list[str], cv_text: str, limit: int = 30) -> list[dict]:
    """Canonicalize names, deduplicate aliases, and reject ungrounded LLM output."""
    evidence_text = normalize_key(cv_text)
    normalized = []
    seen = set()
    for raw in raw_skills:
        key = normalize_key(str(raw))
        if not key or len(key) > 60 or len(key.split()) > 6 or key in TOO_GENERIC:
            continue
        canonical = display_name(key)
        canonical_key = normalize_key(canonical)
        aliases = {key, canonical_key}
        grounded = any(alias and alias in evidence_text for alias in aliases)
        if not grounded:
            continue
        if canonical_key in seen:
            continue
        seen.add(canonical_key)
        normalized.append({
            "skill_id": re.sub(r"[^a-z0-9]+", "-", canonical_key).strip("-"),
            "canonical_name": canonical,
            "display_name_vi": canonical,
            "display_name_en": canonical,
            "category": CATEGORIES.get(canonical, "technical_skill"),
            "is_soft_skill": canonical_key in SOFT_SKILLS,
            "evidence_status": "explicit",
        })
        if len(normalized) >= limit:
            break
    return normalized
