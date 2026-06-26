import os
import json
import logging
import httpx
from fastmcp import FastMCP

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("mcp_server")

mcp = FastMCP("Agent MCP Server")

PROFILE_SCANNER_URL = os.getenv("PROFILE_SCANNER_URL", "http://profile-scanner:8080")
MARKET_SCOUT_URL = os.getenv("MARKET_SCOUT_URL", "http://market-scout:8080")
ACADEMIC_ARCHITECT_URL = os.getenv("ACADEMIC_ARCHITECT_URL", "http://academic-architect:8080")

def _upstream_error_payload(
    method: str,
    url: str,
    endpoint: str,
    exc: Exception,
    response: httpx.Response | None = None
) -> dict:
    payload = {
        "status": "error",
        "method": method,
        "service_url": url,
        "endpoint": endpoint,
        "error_type": type(exc).__name__,
        "error": str(exc),
    }
    if response is not None:
        payload.update({
            "status_code": response.status_code,
            "response_text": response.text[:500],
        })
    return payload

def fetch_data_sync(url: str, endpoint: str, payload: dict) -> dict:
    try:
        response = httpx.post(f"{url}{endpoint}", json=payload, timeout=180.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        error_payload = _upstream_error_payload("POST", url, endpoint, exc, exc.response)
        logger.error("Upstream POST request failed", extra=error_payload)
        return error_payload
    except Exception as exc:
        error_payload = _upstream_error_payload("POST", url, endpoint, exc)
        logger.exception("Upstream POST request failed", extra=error_payload)
        return error_payload

def get_data_sync(url: str, endpoint: str) -> dict:
    try:
        response = httpx.get(f"{url}{endpoint}", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        error_payload = _upstream_error_payload("GET", url, endpoint, exc, exc.response)
        logger.error("Upstream GET request failed", extra=error_payload)
        return error_payload
    except Exception as exc:
        error_payload = _upstream_error_payload("GET", url, endpoint, exc)
        logger.exception("Upstream GET request failed", extra=error_payload)
        return error_payload

@mcp.tool()
def profile_scanner(
    user_id: str,
    background_info: str = "",
    task: str = "scan_profile",
    answers_json: str = "",
    cv_document_id: str = ""
) -> dict:
    """Use this Profile Scanner agent tool for CV/profile scanning and Holland/RIASEC career-interest assessment.

    Supported task values:
    - scan_profile: scan a previously uploaded CV document when cv_document_id is provided.
    - holland_start: start the Holland/RIASEC test and return the question bank.
    - holland_score: score and save completed Holland/RIASEC answers.

    For holland_score, answers_json must be a JSON array like:
    [{"question_id":"R1","score":5},{"question_id":"I1","score":4}]
    Scores are integers from 1 to 5.
    """
    normalized_task = task.strip().lower()

    if normalized_task in {"holland", "holland_start", "riasec", "riasec_start"}:
        return get_data_sync(PROFILE_SCANNER_URL, f"/holland/start/{user_id}")

    if normalized_task in {"holland_score", "riasec_score"} or answers_json.strip():
        if not answers_json.strip():
            return {
                "status": "error",
                "feature": "holland_assessment",
                "error": "answers_json is required when task is holland_score.",
                "expected_format": [{"question_id": "R1", "score": 5}]
            }

        try:
            answers = json.loads(answers_json)
        except json.JSONDecodeError as exc:
            return {
                "status": "error",
                "feature": "holland_assessment",
                "error": f"answers_json must be valid JSON: {exc}",
                "expected_format": [{"question_id": "R1", "score": 5}]
            }

        return fetch_data_sync(PROFILE_SCANNER_URL, "/holland/score", {
            "user_id": user_id,
            "answers": answers,
            "source": "orchestrator_chat"
        })

    return fetch_data_sync(PROFILE_SCANNER_URL, "/scan", {
        "user_id": user_id,
        "background_info": background_info,
        "cv_document_id": cv_document_id
    })

@mcp.tool()
def market_scout(industry: str, target_role: str) -> dict:
    """Use this tool to find market trends, current jobs, and salary expectations. 
    Call this agent if you need information about the job market for a specific role and industry."""
    return fetch_data_sync(MARKET_SCOUT_URL, "/scout", {
        "industry": industry,
        "target_role": target_role
    })

@mcp.tool()
def academic_architect(career_goal: str, user_id: str, current_skills: str = "") -> dict:
    """Use this tool to create a roadmap to achieve a certain job description or career goal. 
    It will perform a skill gap analysis using the user's scanned CV and recommend courses and jobs.
    
    Args:
        career_goal: the user's target career goal (e.g. 'Data Analyst', 'Frontend Engineer')
        user_id: the current user's User ID (Google ID) to lookup their scanned CV
        current_skills: optional comma-separated current skills, if CV is not available
    """
    return fetch_data_sync(ACADEMIC_ARCHITECT_URL, "/architect", {
        "career_goal": career_goal,
        "current_skills": current_skills,
        "user_id": user_id
    })

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8004))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
