import json
import re
from functools import lru_cache
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from core.config import logger, settings
from profile_ai_extraction.schemas import StructuredProfile


MAX_AI_CV_CHARS = 18000


@lru_cache(maxsize=1)
def get_profile_extraction_llm():
    if not settings.profile_ai_extraction_enabled:
        return None

    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.profile_ai_model_name,
        temperature=0,
        vertexai=settings.use_vertex_ai,
        project=settings.google_cloud_project if settings.use_vertex_ai else None,
        location=settings.vertex_ai_location if settings.use_vertex_ai else None,
    )


def message_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def parse_json_object(text: str) -> dict:
    clean_text = text.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```(?:json)?", "", clean_text, flags=re.IGNORECASE).strip()
        clean_text = re.sub(r"```$", "", clean_text).strip()

    try:
        return json.loads(clean_text)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", clean_text)
        if not match:
            raise
        return json.loads(match.group(0))


def build_extraction_prompt(parsed_text: str, target_role: str | None, message: str | None) -> list:
    clipped_text = parsed_text[:MAX_AI_CV_CHARS]
    system_prompt = (
        "You are Profile Scanner's CV structure extractor. "
        "Extract only facts directly supported by the CV text. "
        "Do not invent employers, degrees, dates, skills, scores, or career advice. "
        "For skills, return concise canonical technology or competency names, merge aliases, "
        "preserve standard acronyms, and exclude sentence fragments or generic terms such as API, cloud, software, and web. "
        "Only return a soft skill when the CV explicitly states or demonstrates it. "
        "Use empty strings or empty arrays for unavailable fields; do not return null. "
        "Return one valid JSON object only, without markdown."
    )
    user_prompt = {
        "task": "Extract structured CV profile fields for downstream scoring.",
        "target_role_from_user": target_role or "",
        "user_message": message or "",
        "output_schema": {
            "full_name": "string",
            "email": "string",
            "phone": "string",
            "location": "string",
            "linkedin_url": "string",
            "github_url": "string",
            "portfolio_url": "string",
            "target_role_hint": "string",
            "headline": "string",
            "summary": "string",
            "skills": ["string"],
            "work_experiences": [
                {
                    "title": "string",
                    "organization": "string",
                    "duration": "string",
                    "summary": "string",
                    "skills": ["string"],
                    "impact_evidence": ["string"]
                }
            ],
            "education": [
                {
                    "institution": "string",
                    "degree": "string",
                    "field": "string",
                    "duration": "string",
                    "evidence": "string"
                }
            ],
            "projects": [
                {
                    "name": "string",
                    "summary": "string",
                    "skills": ["string"],
                    "impact_evidence": ["string"],
                    "url": "string"
                }
            ],
            "certifications": ["string"],
            "achievements": ["string"],
            "career_readiness_signals": ["communication|teamwork|leadership|critical thinking|professionalism|technology|career self-development"],
            "missing_or_unclear": ["string"],
            "confidence": 0.0
        },
        "cv_text": clipped_text,
    }
    return [
        SystemMessage(content=system_prompt),
        HumanMessage(content=json.dumps(user_prompt, ensure_ascii=False)),
    ]


def extract_structured_profile_with_ai(
    *,
    parsed_text: str,
    target_role: str | None = None,
    message: str | None = None,
) -> StructuredProfile | None:
    llm = get_profile_extraction_llm()
    if llm is None:
        return None

    try:
        response = llm.invoke(build_extraction_prompt(parsed_text, target_role, message))
        payload = parse_json_object(message_content_to_text(response.content))
        payload["extraction_source"] = "ai"
        return StructuredProfile(**payload)
    except Exception as exc:
        logger.exception(
            "AI structured profile extraction failed; falling back to heuristic analysis",
            extra={"error_type": type(exc).__name__},
        )
        return None
