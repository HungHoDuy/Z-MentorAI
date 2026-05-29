import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"

class ChatResponse(BaseModel):
    response: str

# Set up the LLM
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)

agent = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://mcp-server:8080/sse")
    
    # Initialize MultiServerMCPClient to connect to the MCP server
    client = MultiServerMCPClient({
        "agents": {
            "url": MCP_SERVER_URL,
            "transport": "sse",
        }
    })
    
    # Fetch tools with retry mechanism to handle container startup race conditions
    import asyncio
    for attempt in range(10):
        try:
            tools = await client.get_tools()
            agent = create_react_agent(llm, tools)
            print("Successfully retrieved tools from MCP server.")
            break
        except Exception as e:
            print(f"Attempt {attempt + 1}/10: Failed to fetch tools from MCP server: {e}")
            if attempt == 9:
                raise e
            await asyncio.sleep(2)
    yield

app = FastAPI(title="Orchestrator Agent", lifespan=lifespan)

# System prompt
system_message = SystemMessage(content=(
    "You are the central Orchestrator Agent for a Job Orientation platform. Your ultimate goal is to guide users towards their ideal career. "
    "You have access to specialized agents as tools: Profile Scanner, Market Scout, and Academic Architect. "
    "Based on the user's message, decide which tool(s) to call to gather the necessary information. "
    "Once you have the information, synthesize it and provide a helpful, coherent response to the user. "
    "If you need more information from the user before you can use a tool, ask them directly."
))

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
