import os
import json
import logging
from time import perf_counter
from typing import Any
import httpx
from fastmcp import FastMCP

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
logger = logging.getLogger("mcp_server")

mcp = FastMCP("Agent MCP Server")

PROFILE_SCANNER_URL = os.getenv("PROFILE_SCANNER_URL", "http://profile-scanner:8080")
MARKET_SCOUT_URL = os.getenv("MARKET_SCOUT_URL", "http://market-scout:8080")
ACADEMIC_ARCHITECT_URL = os.getenv("ACADEMIC_ARCHITECT_URL", "http://academic-architect:8080")
def _log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, ensure_ascii=False, default=str))


def _short_text(value: str | None, max_length: int = 500) -> str:
    text = " ".join((value or "").split())
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."

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
    start = perf_counter()
    try:
        response = httpx.post(f"{url}{endpoint}", json=payload, timeout=180.0)
        response.raise_for_status()
        _log_event("mcp_upstream_success", endpoint=endpoint, status_code=response.status_code, duration_ms=round((perf_counter() - start) * 1000, 2))
        return response.json()
    except httpx.HTTPStatusError as exc:
        error_payload = _upstream_error_payload("POST", url, endpoint, exc, exc.response)
        error_payload["duration_ms"] = round((perf_counter() - start) * 1000, 2)
        logger.error(json.dumps({"event": "mcp_upstream_error", **error_payload}, ensure_ascii=False, default=str))
        return error_payload
    except Exception as exc:
        error_payload = _upstream_error_payload("POST", url, endpoint, exc)
        error_payload["duration_ms"] = round((perf_counter() - start) * 1000, 2)
        logger.exception(json.dumps({"event": "mcp_upstream_exception", **error_payload}, ensure_ascii=False, default=str))
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
    sub_agent = "holland_test" if normalized_task in {"holland", "holland_start", "riasec", "riasec_start", "holland_score", "riasec_score"} or answers_json.strip() else "scan_cv"
    _log_event(
        "mcp_tool_call",
        agent="profile_scanner",
        sub_agent=sub_agent,
        user_id=user_id,
        user_query=_short_text(background_info),
        task=normalized_task,
        has_cv_document=bool(cv_document_id),
    )

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
def market_scout(
    industry: str,
    target_role: str = "",
    user_query: str = "",
    intent_hint: str = "",
) -> dict:
    """Use this tool for job market trends, hiring demand, automation exposure, and general market outlook.
    For salary or compensation questions, prefer the salary_benchmark tool.
    If using this tool for salary, pass the original user question in user_query and intent_hint="salary_benchmark"."""
    sub_agent = intent_hint.strip() or ("salary_benchmark" if _looks_like_salary_query(user_query) else "trend_tracker")
    _log_event(
        "mcp_tool_call",
        agent="market_scout",
        sub_agent=sub_agent,
        user_query=_short_text(user_query),
        industry=industry,
        target_role=target_role,
    )
    payload = {
        "industry": industry,
        "target_role": target_role,
    }
    if user_query.strip():
        payload["user_query"] = user_query.strip()
    if intent_hint.strip():
        payload["intent_hint"] = intent_hint.strip()
    elif _looks_like_salary_query(user_query):
        payload["intent_hint"] = "salary_benchmark"

    return fetch_data_sync(MARKET_SCOUT_URL, "/scout", payload)


def _looks_like_salary_query(query: str) -> bool:
    normalized = _normalize_ascii(query)
    salary_keywords = (
        "luong",
        "muc luong",
        "thu nhap",
        "salary",
        "compensation",
        "wage",
        "pay",
    )
    return any(keyword in normalized for keyword in salary_keywords)


def _normalize_ascii(value: str) -> str:
    text = value.casefold().replace(chr(273), "d").replace(chr(272), "d")
    text = "".join(
        character
        for character in __import__("unicodedata").normalize("NFD", text)
        if __import__("unicodedata").category(character) != "Mn"
    )
    return " ".join(text.split())


@mcp.tool()
def salary_benchmark(user_query: str) -> dict:
    """Use this tool when the user asks about salary, compensation, income, wage, pay, or salary benchmark.
    Always pass the original user question as user_query."""
    _log_event("mcp_tool_call", agent="market_scout", sub_agent="salary_benchmark", user_query=_short_text(user_query))
    return fetch_data_sync(MARKET_SCOUT_URL, "/salary-benchmark", {
        "user_query": user_query,
    })


@mcp.tool()
def academic_architect(career_goal: str, user_id: str = "", current_skills: str = "") -> dict:
    """Use this tool to create a roadmap to achieve a certain job description or career goal.
    It will perform a skill gap analysis using the user's scanned CV and recommend courses and jobs.

    Args:
        career_goal: the user's target career goal (e.g. 'Data Analyst', 'Frontend Engineer')
        user_id: the current user's User ID (Google ID) to lookup their scanned CV
        current_skills: optional comma-separated current skills, if CV is not available
    """
    _log_event("mcp_tool_call", agent="academic_architect", sub_agent="roadmap", user_query=_short_text(career_goal), user_id=user_id)
    return fetch_data_sync(ACADEMIC_ARCHITECT_URL, "/architect", {
        "career_goal": career_goal,
        "current_skills": current_skills,
        "user_id": user_id,
    })

@mcp.tool()
def academic_architect_skill_gap(career_goal: str, user_id: str = "", current_skills: str = "") -> dict:
    """Use Case 1: Analyze skill gaps against real job market postings for a career goal."""
    _log_event("mcp_tool_call", agent="academic_architect", sub_agent="skill_gap", user_query=_short_text(career_goal), user_id=user_id)
    return fetch_data_sync(ACADEMIC_ARCHITECT_URL, "/skill-gap", {
        "career_goal": career_goal,
        "current_skills": current_skills,
        "user_id": user_id,
    })

@mcp.tool()
def academic_architect_create_gantt(career_goal: str, lacking_skills: list[str], user_id: str = "") -> dict:
    """Use Case 2: Build structured Gantt chart roadmap & narrative text based on approved lacking skills."""
    _log_event("mcp_tool_call", agent="academic_architect", sub_agent="create_gantt", user_query=_short_text(career_goal), user_id=user_id)
    return fetch_data_sync(ACADEMIC_ARCHITECT_URL, "/create-gantt", {
        "career_goal": career_goal,
        "lacking_skills": lacking_skills,
        "user_id": user_id,
    })

@mcp.tool()
def academic_architect_get_alternatives(chart_id: str, task_id: str, skill_name: str = "") -> dict:
    """Course Swap Step 1: Find top 5 alternative courses in Coursera database for a task."""
    _log_event("mcp_tool_call", agent="academic_architect", sub_agent="get_alternatives", chart_id=chart_id, task_id=task_id)
    return fetch_data_sync(ACADEMIC_ARCHITECT_URL, f"/chart/{chart_id}/get-alternatives", {
        "chart_id": chart_id,
        "task_id": task_id,
        "skill_name": skill_name,
    })

@mcp.tool()
def academic_architect_swap_course(chart_id: str, task_id: str, selected_course_id: str) -> dict:
    """Course Swap Step 2: Swap a task course with selected alternative ID and update Gantt timeline."""
    _log_event("mcp_tool_call", agent="academic_architect", sub_agent="swap_course", chart_id=chart_id, task_id=task_id)
    return fetch_data_sync(ACADEMIC_ARCHITECT_URL, f"/chart/{chart_id}/swap-course", {
        "chart_id": chart_id,
        "task_id": task_id,
        "selected_course_id": selected_course_id,
    })

@mcp.tool()
def academic_architect_input_verifier(
    career_goal: str,
    user_id: str,
    current_skills: str = "",
    action: str = "verify"
) -> dict:
    """Use this tool to present the inputs (career goal and current skills) to the user for validation.
    It will load/save skills from/to the backend and return the inputs for confirmation.
    
    Args:
        career_goal: the user's target career goal (e.g. 'Data Analyst', 'Frontend Engineer')
        user_id: the current user's User ID (Google ID)
        current_skills: optional comma-separated list of skills to set/update. If empty, it loads current skills from backend.
        action: 'verify' to display inputs, 'update' to update skills in database, or 'confirm' when user confirms.
    """
    if action == "update" or (action == "verify" and current_skills.strip()):
        skills_list = [s.strip() for s in current_skills.split(",") if s.strip()]
        res = fetch_data_sync(ACADEMIC_ARCHITECT_URL, f"/skills/{user_id}", {"skills": skills_list})
        return {
            "status": "success",
            "feature": "academic_architect_confirm",
            "career_goal": career_goal,
            "current_skills": skills_list,
            "action": action
        }
    
    # Otherwise verify / load
    res = get_data_sync(ACADEMIC_ARCHITECT_URL, f"/skills/{user_id}")
    skills_list = res.get("skills", [])
    
    return {
        "status": "success",
        "feature": "academic_architect_confirm",
        "career_goal": career_goal,
        "current_skills": skills_list,
        "action": action
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    logger.info("Starting MCP server", extra={"host": "0.0.0.0", "port": port, "transport": "sse"})
    mcp.run(transport="sse", host="0.0.0.0", port=port)