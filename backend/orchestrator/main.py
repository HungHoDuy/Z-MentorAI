import os
import json
import datetime
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langgraph.prebuilt import create_react_agent
import uuid
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from google.oauth2 import id_token
from google.auth.transport import requests

# Determine if we run in GCP/production modes
USE_FIRESTORE = os.getenv("USE_FIRESTORE", "false").lower() == "true"
USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "false").lower() == "true"

# Setup Firestore
firestore_client = None
if USE_FIRESTORE:
    from google.cloud import firestore
    firestore_client = firestore.Client(database="database")
    print("Using Firestore native mode database: 'database'")

# Local JSON fallback databases
USERS_DB_PATH = os.path.join(os.path.dirname(__file__), "users_db.json")
CHAT_DB_PATH = os.path.join(os.path.dirname(__file__), "chat_history_db.json")

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

# Helper functions for database abstractions
async def get_user_by_id(google_id: str) -> Optional[dict]:
    if USE_FIRESTORE:
        doc = firestore_client.collection("user").document(google_id).get()
        return doc.to_dict() if doc.exists else None
    else:
        db = read_users_db()
        return db["users"].get(google_id)

async def save_user(google_id: str, user_data: dict):
    if USE_FIRESTORE:
        firestore_client.collection("user").document(google_id).set(user_data)
    else:
        db = read_users_db()
        db["users"][google_id] = user_data
        write_users_db(db)

async def get_user_sessions(google_id: str) -> list:
    if USE_FIRESTORE:
        docs = firestore_client.collection("history").where("user_id", "==", google_id).stream()
        sessions = [doc.to_dict() for doc in docs]
        sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
        return [
            {
                "id": s["id"],
                "title": s["title"],
                "created_at": s["created_at"]
            }
            for s in sessions
        ]
    else:
        db = read_chat_db()
        user_data = db["users"].get(google_id, {"sessions": {}})
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

async def create_user_session(google_id: str, title: str) -> dict:
    session_id = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat() + "Z"
    session = {
        "id": session_id,
        "title": title,
        "created_at": now,
        "messages": []
    }
    if USE_FIRESTORE:
        session_to_save = session.copy()
        session_to_save["user_id"] = google_id
        firestore_client.collection("history").document(session_id).set(session_to_save)
    else:
        db = read_chat_db()
        user_data = db["users"].setdefault(google_id, {"sessions": {}})
        user_data["sessions"][session_id] = session
        write_chat_db(db)
    return session

async def get_session_details(google_id: str, session_id: str) -> Optional[dict]:
    if USE_FIRESTORE:
        doc = firestore_client.collection("history").document(session_id).get()
        if not doc.exists:
            return None
        session = doc.to_dict()
        if session.get("user_id") != google_id:
            return None
        session.pop("user_id", None)  # remove user_id from returned response
        return session
    else:
        db = read_chat_db()
        user_data = db["users"].get(google_id, {})
        return user_data.get("sessions", {}).get(session_id)

async def delete_user_session(google_id: str, session_id: str) -> bool:
    if USE_FIRESTORE:
        doc_ref = firestore_client.collection("history").document(session_id)
        doc = doc_ref.get()
        if not doc.exists:
            return False
        session = doc.to_dict()
        if session.get("user_id") != google_id:
            return False
        doc_ref.delete()
        return True
    else:
        db = read_chat_db()
        user_data = db["users"].get(google_id, {})
        if session_id in user_data.get("sessions", {}):
            del user_data["sessions"][session_id]
            write_chat_db(db)
            return True
        return False


# Setup the LLM
if USE_VERTEX_AI:
    from langchain_google_vertexai import ChatVertexAI
    llm = ChatVertexAI(
        model_name="gemini-2.5-flash",
        location="asia-southeast1",
        temperature=0.7
    )
    print("Using Vertex AI model gemini-2.5-flash in region asia-southeast1")
else:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
    print("Using Gemini API Key-based ChatGoogleGenerativeAI")

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
    for attempt in range(15):
        try:
            tools = await client.get_tools()
            agent = create_react_agent(llm, tools)
            print("Successfully retrieved tools from MCP server.")
            break
        except Exception as e:
            print(f"Attempt {attempt + 1}/15: Failed to fetch tools from MCP server: {e}")
            if attempt == 14:
                print(f"CRITICAL: Failed to connect to MCP server after 15 attempts. Proceeding with empty tools list: {e}")
                agent = create_react_agent(llm, [])
            else:
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
        
    now = datetime.datetime.utcnow().isoformat() + "Z"
    user = await get_user_by_id(google_id)
    
    if not user:
        user = {
            "google_id": google_id,
            "email": email,
            "name": name,
            "picture": picture,
            "custom_avatar": None,
            "first_login": now,
            "last_login": now
        }
    else:
        user["last_login"] = now
        user["name"] = name or user.get("name")
        if not user.get("custom_avatar"):
            user["picture"] = picture or user.get("picture", "")
            
    await save_user(google_id, user)
    return user


@app.post("/auth/upload-avatar")
async def auth_upload_avatar(request: UploadAvatarRequest):
    user = await get_user_by_id(request.google_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user["custom_avatar"] = request.avatar_base64
    await save_user(request.google_id, user)
    return user

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
    return await get_user_sessions(x_user_id)

@app.post("/sessions")
async def create_session(request: CreateSessionRequest, x_user_id: str = Header(...)):
    return await create_user_session(x_user_id, request.title)

@app.get("/sessions/{session_id}")
async def get_session(session_id: str, x_user_id: str = Header(...)):
    session = await get_session_details(x_user_id, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str, x_user_id: str = Header(...)):
    success = await delete_user_session(x_user_id, session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "success", "message": "Session deleted"}

# System prompt
def get_system_message(user_id: str) -> SystemMessage:
    return SystemMessage(content=(
        "You are the central Orchestrator Agent for a Job Orientation platform. Your ultimate goal is to guide users towards their ideal career. "
        "You have access to specialized agents as tools: Profile Scanner, Market Scout, and Academic Architect. "
        f"The current user's User ID (Google ID) is '{user_id}'. You must use this user ID string when calling the profile_scanner tool. "
        "Based on the user's message, decide which tool(s) to call to gather the necessary information. "
        "Once you have the information, synthesize it and provide a helpful, coherent response to the user. "
        "If you need more information from the user before you can use a tool, ask them directly."
    ))

@app.post("/chat/stream")
async def chat_with_orchestrator_stream(request: ChatRequest, x_user_id: str = Header(...)):
    async def event_generator():
        try:
            session = await get_session_details(x_user_id, request.session_id)
            
            history_messages = []
            if session:
                for msg in session.get("messages", []):
                    if msg["role"] == "user":
                        history_messages.append(HumanMessage(content=msg["content"]))
                    elif msg["role"] == "assistant":
                        history_messages.append(AIMessage(content=msg["content"]))
            
            messages = [get_system_message(x_user_id)] + history_messages + [HumanMessage(content=request.message)]
            
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
                    if hasattr(tool_output, "content"):
                        serializable_output = tool_output.content
                    else:
                        try:
                            json.dumps(tool_output)
                            serializable_output = tool_output
                        except (TypeError, OverflowError):
                            serializable_output = str(tool_output)
                    yield f"data: {json.dumps({'type': 'tool_end', 'tool': name, 'output': serializable_output})}\n\n"
                
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
            await save_chat_exchange(x_user_id, request.session_id, request.message, assistant_content)
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/chat", response_model=ChatResponse)
async def chat_with_orchestrator(request: ChatRequest, x_user_id: str = Header(...)):
    try:
        session = await get_session_details(x_user_id, request.session_id)
        
        history_messages = []
        if session:
            for msg in session.get("messages", []):
                if msg["role"] == "user":
                    history_messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    history_messages.append(AIMessage(content=msg["content"]))
        
        history_messages = trim_history(history_messages, limit=8000)
        messages = [get_system_message(x_user_id)] + history_messages + [HumanMessage(content=request.message)]
        
        result = await agent.ainvoke({"messages": messages})
        content = result["messages"][-1].content
        
        if isinstance(content, list):
            final_response = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block) 
                for block in content
            )
        else:
            final_response = str(content)
            
        await save_chat_exchange(x_user_id, request.session_id, request.message, final_response)
        
        return ChatResponse(response=final_response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "orchestrator"}

# Serve frontend build static files (Option A)
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    print(f"Mounted static frontend files from '{static_dir}'")
else:
    print(f"Static directory '{static_dir}' not found. Frontend serving is disabled.")
