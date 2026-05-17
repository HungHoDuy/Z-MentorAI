import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import asyncio

app = FastAPI(title="Orchestrator Agent")

# Environment variables for service URLs (defaults for docker-compose)
PROFILE_SCANNER_URL = os.getenv("PROFILE_SCANNER_URL", "http://profile-scanner:8080")
MARKET_SCOUT_URL = os.getenv("MARKET_SCOUT_URL", "http://market-scout:8080")
ACADEMIC_ARCHITECT_URL = os.getenv("ACADEMIC_ARCHITECT_URL", "http://academic-architect:8080")

class OrchestratorRequest(BaseModel):
    user_id: str
    background_info: str
    industry: str
    target_role: str
    career_goal: str

class OrchestratorResponse(BaseModel):
    status: str
    profile_analysis: dict
    market_data: dict
    academic_plan: dict
    final_summary: str

async def fetch_data(client, url, endpoint, payload):
    try:
        response = await client.post(f"{url}{endpoint}", json=payload, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except httpx.RequestError as exc:
        print(f"An error occurred while requesting {exc.request.url!r}.")
        return {"error": str(exc)}
    except httpx.HTTPStatusError as exc:
        print(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.")
        return {"error": str(exc)}

@app.post("/orchestrate", response_model=OrchestratorResponse)
async def run_orchestrator(request: OrchestratorRequest):
    async with httpx.AsyncClient() as client:
        # Step 1: Profile Scanner
        profile_task = fetch_data(client, PROFILE_SCANNER_URL, "/scan", {
            "user_id": request.user_id,
            "background_info": request.background_info
        })
        
        # Step 2: Market Scout
        market_task = fetch_data(client, MARKET_SCOUT_URL, "/scout", {
            "industry": request.industry,
            "target_role": request.target_role
        })
        
        # Step 3: Academic Architect
        architect_task = fetch_data(client, ACADEMIC_ARCHITECT_URL, "/architect", {
            "career_goal": request.career_goal,
            # Ideally this would depend on the output of the profile scanner,
            # but we run them in parallel for this simple test if possible.
            # To simulate a pipeline, we might await profile_task first.
            # Let's just pass the background info as current_skills for now.
            "current_skills": request.background_info
        })

        # Run all requests
        profile_res, market_res, architect_res = await asyncio.gather(
            profile_task, market_task, architect_task
        )

    # Langchain could be used here to summarize the results.
    # For now, we mock the final summary.
    final_summary = "Orchestration complete. Gathered profile, market, and academic data."

    return OrchestratorResponse(
        status="success",
        profile_analysis=profile_res,
        market_data=market_res,
        academic_plan=architect_res,
        final_summary=final_summary
    )

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "orchestrator"}
