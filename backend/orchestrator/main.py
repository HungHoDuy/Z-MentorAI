import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

app = FastAPI(title="Orchestrator Agent")

# Environment variables for service URLs
PROFILE_SCANNER_URL = os.getenv("PROFILE_SCANNER_URL", "http://profile-scanner:8080")
MARKET_SCOUT_URL = os.getenv("MARKET_SCOUT_URL", "http://market-scout:8080")
ACADEMIC_ARCHITECT_URL = os.getenv("ACADEMIC_ARCHITECT_URL", "http://academic-architect:8080")

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"

class ChatResponse(BaseModel):
    response: str

# Helper to make HTTP requests
def fetch_data_sync(url: str, endpoint: str, payload: dict) -> dict:
    try:
        response = httpx.post(f"{url}{endpoint}", json=payload, timeout=10.0)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        return {"error": str(exc)}

# Define LangChain Tools
@tool
def profile_scanner(user_id: str, background_info: str) -> dict:
    """Use this tool to scan a user's CV or background to identify their likeliness, profession, and skills. 
    Call this agent if you want to know more about the user's current profile."""
    return fetch_data_sync(PROFILE_SCANNER_URL, "/scan", {
        "user_id": user_id,
        "background_info": background_info
    })

@tool
def market_scout(industry: str, target_role: str) -> dict:
    """Use this tool to find market trends, current jobs, and salary expectations. 
    Call this agent if you need information about the job market for a specific role and industry."""
    return fetch_data_sync(MARKET_SCOUT_URL, "/scout", {
        "industry": industry,
        "target_role": target_role
    })

@tool
def academic_architect(career_goal: str, current_skills: str) -> dict:
    """Use this tool to create a roadmap to achieve a certain job description or career goal. 
    It will provide data on courses needed to complete and skills needed to acquire."""
    return fetch_data_sync(ACADEMIC_ARCHITECT_URL, "/architect", {
        "career_goal": career_goal,
        "current_skills": current_skills
    })

tools = [profile_scanner, market_scout, academic_architect]

# Set up the LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)

# System prompt
system_message = SystemMessage(content=(
    "You are the central Orchestrator Agent for a Job Orientation platform. Your ultimate goal is to guide users towards their ideal career. "
    "You have access to 3 specialized agents as tools: Profile Scanner, Market Scout, and Academic Architect. "
    "Based on the user's message, decide which tool(s) to call to gather the necessary information. "
    "Once you have the information, synthesize it and provide a helpful, coherent response to the user. "
    "If you need more information from the user before you can use a tool, ask them directly."
))

# Create the Agent
agent = create_react_agent(llm, tools)

@app.post("/chat", response_model=ChatResponse)
async def chat_with_orchestrator(request: ChatRequest):
    try:
        # Run the agent
        messages = [system_message, HumanMessage(content=request.message)]
        result = await agent.ainvoke({"messages": messages})
        
        # The final response is the last message from the AI
        content = result["messages"][-1].content
        
        if isinstance(content, list):
            # Gemini sometimes returns a list of content blocks
            final_response = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block) 
                for block in content
            )
        else:
            final_response = str(content)
            
        return ChatResponse(response=final_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "orchestrator"}
