import os
import json
import datetime
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
import uuid
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from google.oauth2 import id_token
from google.auth.transport import requests

USERS_DB_PATH = os.path.join(os.path.dirname(__file__), "users_db.json")

def read_users_db() -> dict:
    if not os.path.exists(USERS_DB_PATH):
        return {"users": {}}
    try:
        with open(USERS_DB_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}

def write_users_db(db: dict):
    with open(USERS_DB_PATH, "w") as f:
        json.dump(db, f, indent=2)

CHAT_DB_PATH = os.path.join(os.path.dirname(__file__), "chat_history_db.json")

def read_chat_db() -> dict:
    if not os.path.exists(CHAT_DB_PATH):
        return {"users": {}}
    try:
        with open(CHAT_DB_PATH, "r") as f:
            return json.load(f)
    except Exception:
        return {"users": {}}

def write_chat_db(db: dict):
    with open(CHAT_DB_PATH, "w") as f:
        json.dump(db, f, indent=2)


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"

class ChatResponse(BaseModel):
    response: str

class LoginRequest(BaseModel):
    token: str

class UploadAvatarRequest(BaseModel):
    google_id: str
    avatar_base64: str


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

# Enable CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/auth/config")
async def auth_config():
    return {"google_client_id": os.getenv("GOOGLE_CLIENT_ID", "")}

@app.post("/auth/login")
async def auth_login(request: LoginRequest):
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google Client ID is not configured on the server.")
    
    try:
        idinfo = id_token.verify_oauth2_token(request.token, requests.Request(), GOOGLE_CLIENT_ID)
        google_id = idinfo.get("sub")
        email = idinfo.get("email")
        name = idinfo.get("name")
        picture = idinfo.get("picture", "")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google ID Token: {str(e)}")
            
    if not google_id or not email:
        raise HTTPException(status_code=400, detail="Missing user identifiers")
        
    db = read_users_db()
    now = datetime.datetime.utcnow().isoformat() + "Z"
    
    if google_id not in db["users"]:
        db["users"][google_id] = {
            "google_id": google_id,
            "email": email,
            "name": name,
            "picture": picture,
            "custom_avatar": None,
            "first_login": now,
            "last_login": now
        }
    else:
        user = db["users"][google_id]
        user["last_login"] = now
        user["name"] = name or user.get("name")
        if not user.get("custom_avatar"):
            user["picture"] = picture or user.get("picture", "")
            
    write_users_db(db)
    return db["users"][google_id]


@app.post("/auth/upload-avatar")
async def auth_upload_avatar(request: UploadAvatarRequest):
    db = read_users_db()
    if request.google_id not in db["users"]:
        raise HTTPException(status_code=404, detail="User not found")
        
    db["users"][request.google_id]["custom_avatar"] = request.avatar_base64
    write_users_db(db)
    return db["users"][request.google_id]

def trim_history(messages_list: list, limit: int = 8000) -> list:
    while len(messages_list) > 0:
        total_tokens = sum(llm.get_num_tokens(str(m.content)) for m in messages_list)
        if total_tokens <= limit:
            break
        if len(messages_list) >= 2:
            messages_list = messages_list[2:]
        else:
            messages_list = messages_list[1:]
    return messages_list

class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Chat"

@app.get("/sessions")
async def get_sessions(x_user_id: str = Header(...)):
    db = read_chat_db()
    user_data = db["users"].get(x_user_id, {"sessions": {}})
    sessions = list(user_data["sessions"].values())
    sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return [
        {
            "id": s["id"],
            "title": s["title"],
            "created_at": s["created_at"]
        }
        for s in sessions
    ]

@app.post("/sessions")
async def create_session(request: CreateSessionRequest, x_user_id: str = Header(...)):
    db = read_chat_db()
    user_data = db["users"].setdefault(x_user_id, {"sessions": {}})
    session_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat() + "Z"
    
    session = {
        "id": session_id,
        "title": request.title,
        "created_at": now,
        "messages": []
    }
    user_data["sessions"][session_id] = session
    write_chat_db(db)
    return session

@app.get("/sessions/{session_id}")
async def get_session(session_id: str, x_user_id: str = Header(...)):
    db = read_chat_db()
    user_data = db["users"].get(x_user_id, {})
    session = user_data.get("sessions", {}).get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, x_user_id: str = Header(...)):
    db = read_chat_db()
    user_data = db["users"].get(x_user_id, {})
    if session_id in user_data.get("sessions", {}):
        del user_data["sessions"][session_id]
        write_chat_db(db)
        return {"status": "success", "message": "Session deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

# System prompt
system_message = SystemMessage(content=(
    "You are the central Orchestrator Agent for a Job Orientation platform. Your ultimate goal is to guide users towards their ideal career. "
    "You have access to specialized agents as tools: Profile Scanner, Market Scout, and Academic Architect. "
    "Based on the user's message, decide which tool(s) to call to gather the necessary information. "
    "Once you have the information, synthesize it and provide a helpful, coherent response to the user. "
    "If you need more information from the user before you can use a tool, ask them directly."
))

@app.post("/chat/stream")
async def chat_with_orchestrator_stream(request: ChatRequest, x_user_id: str = Header(...)):
    async def event_generator():
        try:
            chat_db = read_chat_db()
            user_data = chat_db["users"].setdefault(x_user_id, {"sessions": {}})
            session = user_data["sessions"].get(request.session_id)
            
            history_messages = []
            if session:
                for msg in session.get("messages", []):
                    if msg["role"] == "user":
                        history_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        history_messages.append(AIMessage(content=msg["content"]))
            
            messages = [system_message] + history_messages + [HumanMessage(content=request.message)]
            
            print(f"DEBUG STREAM x_user_id={x_user_id} session_id={request.session_id}")
            print(f"DEBUG STREAM messages count={len(messages)}")
            for m in messages:
                print(f"  - {m.__class__.__name__}: {repr(m.content)}")
            
            assistant_content = ""
            
            async for event in agent.astream_events({"messages": messages}, version="v2"):
                event_type = event["event"]
                name = event["name"]
                
                if event_type == "on_tool_start":
                    tool_input = event["data"].get("input")
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': name, 'input': tool_input})}\n\n"
                
                elif event_type == "on_tool_end":
                    tool_output = event["data"].get("output")
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': name, 'output': tool_output})}\n\n"
                
                elif event_type == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if chunk:
                        if hasattr(chunk, "tool_calls") and chunk.tool_calls:
                            continue
                        content = chunk.content
                        if content:
                            if isinstance(content, list):
                                text = "".join(
                                    block.get("text", "") if isinstance(block, dict) else str(block)
                                    for block in content
                                )
                            else:
                                text = str(content)
                            if text:
                                assistant_content += text
                                yield f"data: {json.dumps({'type': 'token', 'content': text})}\n\n"
                                
            # Save the exchange to history
            chat_db = read_chat_db()
            user_data = chat_db["users"].setdefault(x_user_id, {"sessions": {}})
            
            if request.session_id not in user_data["sessions"]:
                now = datetime.datetime.utcnow().isoformat() + "Z"
                user_data["sessions"][request.session_id] = {
                    "id": request.session_id,
                    "title": "New Chat",
                    "created_at": now,
                    "messages": []
                }
            
            session = user_data["sessions"][request.session_id]
            session["messages"].append({"role": "user", "content": request.message})
            session["messages"].append({"role": "assistant", "content": assistant_content})
            
            if session.get("title") == "New Chat":
                try:
                    title_prompt = f"Generate a short conversation title (2 to 4 words) summarizing the following user message. Return ONLY the title text, with no quotes, formatting, or extra explanation.\nUser Message: {request.message}"
                    res = await llm.ainvoke(title_prompt)
                    new_title = res.content.strip().replace('"', '').replace("'", "")
                    if new_title:
                        session["title"] = new_title
                    else:
                        session["title"] = request.message[:30] + ("..." if len(request.message) > 30 else "")
                except Exception as e:
                    print(f"Error generating session title: {e}")
                    session["title"] = request.message[:30] + ("..." if len(request.message) > 30 else "")
                
            write_chat_db(chat_db)
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/chat", response_model=ChatResponse)
async def chat_with_orchestrator(request: ChatRequest, x_user_id: str = Header(...)):
    try:
        chat_db = read_chat_db()
        user_data = chat_db["users"].setdefault(x_user_id, {"sessions": {}})
        session = user_data["sessions"].get(request.session_id)
        
        history_messages = []
        if session:
            for msg in session.get("messages", []):
                if msg["role"] == "user":
                    history_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    history_messages.append(AIMessage(content=msg["content"]))
        
        history_messages = trim_history(history_messages, limit=8000)
        messages = [system_message] + history_messages + [HumanMessage(content=request.message)]
        
        result = await agent.ainvoke({"messages": messages})
        content = result["messages"][-1].content
        
        if isinstance(content, list):
            final_response = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block) 
                for block in content
            )
        else:
            final_response = str(content)
            
        chat_db = read_chat_db()
        user_data = chat_db["users"].setdefault(x_user_id, {"sessions": {}})
        
        if request.session_id not in user_data["sessions"]:
            now = datetime.datetime.utcnow().isoformat() + "Z"
            user_data["sessions"][request.session_id] = {
                "id": request.session_id,
                "title": "New Chat",
                "created_at": now,
                "messages": []
            }
            
        session = user_data["sessions"][request.session_id]
        session["messages"].append({"role": "user", "content": request.message})
        session["messages"].append({"role": "assistant", "content": final_response})
        
        if session.get("title") == "New Chat":
            try:
                title_prompt = f"Generate a short conversation title (2 to 4 words) summarizing the following user message. Return ONLY the title text, with no quotes, formatting, or extra explanation.\nUser Message: {request.message}"
                res = await llm.ainvoke(title_prompt)
                new_title = res.content.strip().replace('"', '').replace("'", "")
                if new_title:
                    session["title"] = new_title
                else:
                    session["title"] = request.message[:30] + ("..." if len(request.message) > 30 else "")
            except Exception as e:
                print(f"Error generating session title: {e}")
                session["title"] = request.message[:30] + ("..." if len(request.message) > 30 else "")
            
        write_chat_db(chat_db)
        
        return ChatResponse(response=final_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "orchestrator"}
