import os
import json
import httpx
from fastmcp import FastMCP

mcp = FastMCP("Agent MCP Server")

PROFILE_SCANNER_URL = os.getenv("PROFILE_SCANNER_URL", "http://profile-scanner:8080")
MARKET_SCOUT_URL = os.getenv("MARKET_SCOUT_URL", "http://market-scout:8080")
ACADEMIC_ARCHITECT_URL = os.getenv("ACADEMIC_ARCHITECT_URL", "http://academic-architect:8080")

def fetch_data_sync(url: str, endpoint: str, payload: dict) -> dict:
    try:
        response = httpx.post(f"{url}{endpoint}", json=payload, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"error": str(exc)}

def get_data_sync(url: str, endpoint: str) -> dict:
    try:
        response = httpx.get(f"{url}{endpoint}", timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"error": str(exc)}

@mcp.tool()
def profile_scanner(user_id: str, background_info: str) -> dict:
    """Use this tool to scan a user's CV or background to identify their likeliness, profession, and skills. 
    Call this agent if you want to know more about the user's current profile."""
    return fetch_data_sync(PROFILE_SCANNER_URL, "/scan", {
        "user_id": user_id,
        "background_info": background_info
    })

@mcp.tool()
def holland_test(user_id: str, answers_json: str = "") -> dict:
    """Use this tool for Holland/RIASEC career-interest testing.

    Call with an empty answers_json string when the user wants to start the test; it returns the question bank and scoring scale.
    Call with answers_json when the user has answered. answers_json must be a JSON array like:
    [{"question_id":"R1","score":5},{"question_id":"I1","score":4}]
    Scores are integers from 1 to 5.
    """
    if not answers_json.strip():
        return get_data_sync(PROFILE_SCANNER_URL, f"/holland/start/{user_id}")

    try:
        answers = json.loads(answers_json)
    except json.JSONDecodeError as exc:
        return {
            "error": f"answers_json must be valid JSON: {exc}",
            "expected_format": [{"question_id": "R1", "score": 5}]
        }

    return fetch_data_sync(PROFILE_SCANNER_URL, "/holland/score", {
        "user_id": user_id,
        "answers": answers,
        "source": "orchestrator_chat"
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
def academic_architect(career_goal: str, current_skills: str) -> dict:
    """Use this tool to create a roadmap to achieve a certain job description or career goal. 
    It will provide data on courses needed to complete and skills needed to acquire."""
    return fetch_data_sync(ACADEMIC_ARCHITECT_URL, "/architect", {
        "career_goal": career_goal,
        "current_skills": current_skills
    })

if __name__ == "__main__":
    mcp.run(transport="sse", host="0.0.0.0", port=8080)
