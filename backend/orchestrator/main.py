import os
import json
import re
import datetime
from typing import Any, Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langgraph.prebuilt import create_react_agent
import uuid
import httpx
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from google.oauth2 import id_token
from google.auth.transport import requests
from pathlib import Path
from dotenv import load_dotenv
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestrator")

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"Orchestrator: Loaded environment from {env_path}")
else:
    print("Orchestrator: Warning, no .env file found.")

# Determine if we run in GCP/production modes
USE_FIRESTORE = os.getenv("USE_FIRESTORE", "false").lower() == "true"
USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "false").lower() == "true"

# Setup Firestore
firestore_client = None
if USE_FIRESTORE:
    from google.cloud import firestore
    db_name = os.getenv("FIRESTORE_DATABASE")
    if db_name and db_name != "(default)":
        firestore_client = firestore.Client(database=db_name)
        print(f"Using Firestore native mode database: '{db_name}'")
    else:
        firestore_client = firestore.Client()
        print("Using Firestore native mode database: '(default)'")

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


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default_session"
    attachment: Optional[dict[str, Any]] = None

class ChatResponse(BaseModel):
    response: str

class LoginRequest(BaseModel):
    token: str

class UploadAvatarRequest(BaseModel):
    google_id: str
    avatar_base64: str


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    target_role: Optional[str] = None


class SettingsUpdateRequest(BaseModel):
    language: Optional[str] = None
    theme: Optional[str] = None


PROFILE_EDITABLE_FIELDS = {
    "name", "phone", "location", "linkedin_url", "github_url",
    "portfolio_url", "target_role",
}


def require_known_user(user_id: str) -> dict:
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing user identity")
    if USE_FIRESTORE:
        snapshot = firestore_client.collection("user").document(user_id).get()
        if not snapshot.exists:
            raise HTTPException(status_code=401, detail="Unknown user")
        return snapshot.to_dict()
    user = read_users_db().get("users", {}).get(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Unknown user")
    return user


def get_profile_workspace(user_id: str) -> dict:
    user = require_known_user(user_id)
    preferences = user.get("preferences") or {"language": "vi", "theme": "light"}
    canonical = None
    active_document = None
    if USE_FIRESTORE:
        profile_snapshot = firestore_client.collection(
            os.getenv("PROFILE_SCANNER_PROFILES_COLLECTION", "profile_scanner_profiles")
        ).document(user_id).get()
        canonical = profile_snapshot.to_dict() if profile_snapshot.exists else None
        active_document_id = (canonical or {}).get("active_cv_document_id")
        if active_document_id:
            document_snapshot = firestore_client.collection(
                os.getenv("CV_DOCUMENTS_COLLECTION", "profile_scanner_cv_documents")
            ).document(active_document_id).get()
            active_document = document_snapshot.to_dict() if document_snapshot.exists else None

    identity = (canonical or {}).get("identity") or {}
    return {
        "user_id": user_id,
        "email": user.get("email", ""),
        "name": user.get("name") or identity.get("full_name") or "",
        "picture": user.get("picture", ""),
        "custom_avatar": user.get("custom_avatar"),
        "phone": user.get("phone") or identity.get("phone") or "",
        "location": user.get("location") or identity.get("location") or "",
        "linkedin_url": user.get("linkedin_url") or identity.get("linkedin_url") or "",
        "github_url": user.get("github_url") or identity.get("github_url") or "",
        "portfolio_url": user.get("portfolio_url") or identity.get("portfolio_url") or "",
        "target_role": user.get("target_role") or (canonical or {}).get("target_role") or "",
        "preferences": preferences,
        "current_cv": None if not canonical else {
            "cv_document_id": canonical.get("active_cv_document_id"),
            "original_filename": (active_document or {}).get("original_filename"),
            "uploaded_at": (active_document or {}).get("uploaded_at"),
            "grade": canonical.get("grade"),
            "total_score": canonical.get("total_score"),
            "headline": canonical.get("headline"),
            "summary": canonical.get("summary"),
            "skills": canonical.get("normalized_skills") or canonical.get("skills") or [],
            "profile_version": canonical.get("profile_version"),
        },
    }


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

def message_content_to_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, list):
        return "".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        )
    return str(content)


def serialize_tool_output(tool_output: Any) -> Any:
    if hasattr(tool_output, "content"):
        return tool_output.content

    try:
        json.dumps(tool_output)
        return tool_output
    except (TypeError, OverflowError):
        return str(tool_output)


def normalize_tool_output(output: Any) -> dict:
    if isinstance(output, dict):
        return output
    if isinstance(output, list):
        text_part = next(
            (
                part.get("text")
                for part in output
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ),
            "",
        )
        return normalize_tool_output(text_part)
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def summarize_tool_calls(tool_calls: list[dict]) -> str:
    for tool_call in tool_calls:
        name = tool_call.get("name")
        if name in {"academic_architect", "academic_architect_create_gantt"}:
            return "Đã xây dựng lộ trình học tập Gantt Chart và gợi ý các khóa học phù hợp."
        elif name == "academic_architect_skill_gap":
            return "Đã phân tích khoảng cách kỹ năng từ dữ liệu tuyển dụng thực tế."
        elif name == "academic_architect_swap_course":
            return "Đã cập nhật khóa học thay thế vào lộ trình Gantt Chart."
        elif name == "academic_architect_input_verifier":
        output = normalize_tool_output(tool_call.get("output"))
        if name == "academic_architect":
            return "Đã xây dựng lộ trình học tập và gợi ý các khóa học phù hợp."
        if name == "academic_architect_input_verifier":
            return "Đã chuẩn bị thông tin đầu vào (mục tiêu nghề nghiệp & kỹ năng) để xác nhận."
        if name == "market_scout":
            return "Đã tìm kiếm xu hướng thị trường và thông tin tuyển dụng."
        if name == "profile_scanner":
            if output.get("feature") == "profile_confirmation":
                return output.get("message_vi", "Đã cập nhật trạng thái hồ sơ cá nhân.")
            if output.get("feature") == "career_alignment":
                return "Đã tổng hợp mức độ phù hợp giữa CV, Holland và MI."
            if output.get("feature") == "assessment":
                if output.get("questions"):
                    return f"Đã tạo biểu mẫu {output.get('title', 'assessment')}."
                if output.get("top_dimensions"):
                    return f"Đã chấm điểm {output.get('title', 'assessment')}."
            if output.get("feature") == "holland_assessment":
                if output.get("questions"):
                    return "Đã tạo biểu mẫu Holland Test."
                if output.get("top_code"):
                    return "Đã chấm điểm Holland Test và lưu kết quả RIASEC."
            if output.get("feature") == "profile_scan" or "extracted_skills" in output or "grade" in output:
                profile_action = output.get("profile_action") or {}
                if profile_action.get("message_vi"):
                    return profile_action["message_vi"]
                return "Đã quét và phân tích hồ sơ/CV của bạn."
    return "Agent đã hoàn tất bước xử lý."

def sanitize_user_message_for_history(user_message: str) -> str:
    content = (user_message or "").strip()
    if not content:
        return ""

    if "holland_score" not in content and "assessment_score" not in content and "answers_json" not in content:
        return content

    answered_count = None
    json_match = (
        re.search(r"```json\s*([\s\S]*?)\s*```", content)
        or re.search(r"answers_json\s*(?:sau)?:\s*(\[[\s\S]*\])", content)
    )
    if json_match:
        try:
            answers = json.loads(json_match.group(1))
            if isinstance(answers, list):
                answered_count = len(answers)
        except json.JSONDecodeError:
            answered_count = None

    if answered_count:
        if "assessment_score" in content or "multiple_intelligences" in content:
            return (
                f"Mình đã hoàn thành bài MI với {answered_count} câu trả lời. "
                "Hãy chấm điểm và lưu kết quả Multiple Intelligences vào hồ sơ của mình."
            )
        return (
            f"Mình đã hoàn thành Holland Test với {answered_count} câu trả lời. "
            "Hãy chấm điểm và lưu kết quả RIASEC vào hồ sơ của mình."
        )

    if "assessment_score" in content or "multiple_intelligences" in content:
        return (
            "Mình đã hoàn thành bài MI. "
            "Hãy chấm điểm và lưu kết quả Multiple Intelligences vào hồ sơ của mình."
        )

    return (
        "Mình đã hoàn thành Holland Test. "
        "Hãy chấm điểm và lưu kết quả RIASEC vào hồ sơ của mình."
    )


def build_history_messages(session: Optional[dict]) -> list:
    history_messages = []
    if not session:
        return history_messages

    for msg in session.get("messages", []):
        content = message_content_to_text(msg.get("content")).strip()
        if not content:
            continue

        if msg.get("role") == "user":
            history_messages.append(HumanMessage(content=content))
        elif msg.get("role") == "assistant":
            history_messages.append(AIMessage(content=content))

    return history_messages


async def save_chat_exchange(
    google_id: str,
    session_id: str,
    user_message: str,
    assistant_message: str,
    assistant_tool_calls: Optional[list[dict]] = None,
    user_attachment: Optional[dict[str, Any]] = None,
):
    session = await get_session_details(google_id, session_id)
    now = datetime.datetime.utcnow().isoformat() + "Z"
    assistant_tool_calls = assistant_tool_calls or []
    
    if not session:
        session = {
            "id": session_id,
            "title": "New Chat",
            "created_at": now,
            "messages": []
        }
    
    if user_attachment:
        stored_user_message = next(
            (line.strip() for line in (user_message or "").splitlines() if line.strip()),
            "",
        )
    else:
        stored_user_message = sanitize_user_message_for_history(user_message)
    if stored_user_message:
        user_record = {"role": "user", "content": stored_user_message}
        if user_attachment:
            user_record["attachment"] = user_attachment
        session["messages"].append(user_record)

    assistant_content = (assistant_message or "").strip()
    if assistant_tool_calls and not assistant_content:
        assistant_content = summarize_tool_calls(assistant_tool_calls)

    if assistant_content or assistant_tool_calls:
        assistant_record = {"role": "assistant", "content": assistant_content}
        if assistant_tool_calls:
            assistant_record["tool_calls"] = assistant_tool_calls
        session["messages"].append(assistant_record)
    
    if session.get("title") in ("New Chat", "Cuộc trò chuyện mới"):
        try:
            title_prompt = f"Generate a short conversation title (2 to 4 words) summarizing the following user message. Return ONLY the title text, with no quotes, formatting, or extra explanation.\nUser Message: {user_message}"
            res = await llm.ainvoke([HumanMessage(content=title_prompt)])
            new_title = res.content.strip().replace('"', '').replace("'", "")
            if new_title:
                session["title"] = new_title
            else:
                session["title"] = user_message[:30] + ("..." if len(user_message) > 30 else "")
        except Exception as e:
            print(f"Error generating session title: {e}")
            session["title"] = user_message[:30] + ("..." if len(user_message) > 30 else "")
            
    if USE_FIRESTORE:
        session_to_save = session.copy()
        session_to_save["user_id"] = google_id
        firestore_client.collection("history").document(session_id).set(session_to_save)
    else:
        db = read_chat_db()
        user_data = db["users"].setdefault(google_id, {"sessions": {}})
        user_data["sessions"][session_id] = session
        write_chat_db(db)

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
    return {
        "google_client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
    }

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


@app.get("/me/profile")
async def get_my_profile(x_user_id: str = Header(...)):
    return get_profile_workspace(x_user_id)


@app.patch("/me/profile")
async def update_my_profile(request: ProfileUpdateRequest, x_user_id: str = Header(...)):
    user = require_known_user(x_user_id)
    updates = request.model_dump(exclude_none=True)
    for key in list(updates):
        if key not in PROFILE_EDITABLE_FIELDS:
            updates.pop(key)
            continue
        if isinstance(updates[key], str):
            updates[key] = updates[key].strip()
    user.update(updates)
    user["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await save_user(x_user_id, user)
    return get_profile_workspace(x_user_id)


@app.patch("/me/settings")
async def update_my_settings(request: SettingsUpdateRequest, x_user_id: str = Header(...)):
    user = require_known_user(x_user_id)
    updates = request.model_dump(exclude_none=True)
    language = updates.get("language", (user.get("preferences") or {}).get("language", "vi"))
    theme = updates.get("theme", (user.get("preferences") or {}).get("theme", "light"))
    if language not in {"vi", "en"}:
        raise HTTPException(status_code=422, detail="language must be vi or en")
    if theme not in {"light", "dark"}:
        raise HTTPException(status_code=422, detail="theme must be light or dark")
    user["preferences"] = {"language": language, "theme": theme}
    user["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    await save_user(x_user_id, user)
    return user["preferences"]


@app.post("/profile-scanner/cv/upload")
async def upload_cv_to_profile_scanner(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    target_role: Optional[str] = Form(None),
    message: Optional[str] = Form(None),
    x_user_id: str = Header(...),
):
    profile_scanner_url = os.getenv("PROFILE_SCANNER_URL", "http://profile-scanner:8080")
    endpoint = f"{profile_scanner_url}/cv/intake"
    content = await file.read()

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                endpoint,
                data={
                    "user_id": x_user_id,
                    "session_id": session_id or "",
                    "target_role": target_role or "",
                    "message": message or "",
                },
                files={
                    "file": (
                        file.filename or "cv",
                        content,
                        file.content_type or "application/octet-stream",
                    )
                },
            )
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Unable to reach Profile Scanner CV intake service: {exc}",
        ) from exc

    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise HTTPException(status_code=response.status_code, detail=detail)

    return response.json()

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

def parse_workload_to_weeks_and_hours(workload_str: str) -> tuple[int, float]:
    """
    Parses workload string like '3 weeks of study, 4-5 hours/week'
    and returns (weeks, hours_per_session).
    Assuming study 3 times a week (Mon, Wed, Fri), hours per session = hours/week / 3.
    """
    import re
    if not workload_str:
        return 4, 1.5  # default 4 weeks, 1.5h per session
        
    val_str = str(workload_str).lower()
    
    # 1. Parse weeks
    weeks = 4
    weeks_match = re.search(r'(\d+)\s*(week|tuần|wk)', val_str)
    if weeks_match:
        weeks = int(weeks_match.group(1))
    else:
        months_match = re.search(r'(\d+)\s*(month|tháng|mth)', val_str)
        if months_match:
            weeks = int(months_match.group(1)) * 4
            
    # 2. Parse hours per week
    hours_per_week = 5.0
    hours_match = re.search(r'(\d+)-?(\d+)?\s*(hour|giờ|hr|hrs)', val_str)
    if hours_match:
        if hours_match.group(2): # e.g. 4-5 hours
            hours_per_week = float(hours_match.group(2))
        else:
            hours_per_week = float(hours_match.group(1))
            
    # Study 3 times a week (Mon, Wed, Fri)
    hours_per_session = round(hours_per_week / 3.0, 1)
    if hours_per_session < 0.5:
        hours_per_session = 1.0
        
    return weeks, hours_per_session

def parse_duration_to_days(duration_str: str) -> int:
    """
    Parses duration string like '15 giờ', '3 tháng', '6 tháng', etc.
    and returns estimated number of study days required.
    """
    import re
    import math
    if not duration_str:
        return 7
    val_str = str(duration_str).lower()
    
    # Months
    months_match = re.search(r'(\d+)\s*(tháng|month|mth)', val_str)
    if months_match:
        return int(months_match.group(1)) * 30
        
    # Weeks
    weeks_match = re.search(r'(\d+)\s*(tuần|week|wk)', val_str)
    if weeks_match:
        return int(weeks_match.group(1)) * 7
        
    # Hours
    hours_match = re.search(r'(\d+)\s*(giờ|hour|hr|hrs)', val_str)
    if hours_match:
        hours = int(hours_match.group(1))
        # Study 2 hours per day
        return max(1, math.ceil(hours / 2.0))
        
    # Plain number
    num_match = re.search(r'(\d+)', val_str)
    if num_match:
        val = int(num_match.group(1))
        if val <= 12: # likely months
            return val * 30
        else: # likely hours
            return max(1, math.ceil(val / 2.0))
            
    return 7

class CalendarAppendRequest(BaseModel):
    career_goal: str
    lacking_skills: list[str]
    courses: list[dict]



@app.post("/calendar/generate-schedule")
async def generate_schedule(request: CalendarAppendRequest, x_user_id: str = Header(...)):
    logger.info(f"Calendar: Generating schedule for user {x_user_id} towards target '{request.career_goal}'")
    try:
        import datetime
        today = datetime.date.today()
        current_day_offset = 1  # start tomorrow
        
        events = []
        for i, course in enumerate(request.courses):
            workload_str = course.get('workload')
            duration_str = course.get('duration') or '15 giờ'
            
            # Start date for this course sequence
            start_date = today + datetime.timedelta(days=current_day_offset)
            start_time = datetime.datetime.combine(start_date, datetime.time(9, 0)).isoformat()
            
            if workload_str:
                weeks, hours_per_session = parse_workload_to_weeks_and_hours(workload_str)
                duration_minutes = int(hours_per_session * 60)
                end_dt = datetime.datetime.combine(start_date, datetime.time(9, 0)) + datetime.timedelta(minutes=duration_minutes)
                end_time = end_dt.isoformat()
                
                event_body = {
                    'summary': f"🎓 [Z-Mentor] {course.get('name')}",
                    'description': (
                        f"Lộ trình học tập cho mục tiêu: {request.career_goal}\n"
                        f"🔗 Link khóa học: {course.get('url')}\n"
                        f"⏱️ Khối lượng học: {workload_str} ({weeks} tuần, học {hours_per_session}h vào thứ Hai, Tư, Sáu)\n\n"
                        f"Được tạo tự động bởi Z-MentorAI."
                    ),
                    'start': {
                        'dateTime': start_time,
                        'timeZone': 'Asia/Ho_Chi_Minh',
                    },
                    'end': {
                        'dateTime': end_time,
                        'timeZone': 'Asia/Ho_Chi_Minh',
                    },
                    'recurrence': [
                        f'RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;COUNT={weeks * 3}'
                    ],
                    'reminders': {
                        'useDefault': False,
                        'overrides': [
                            {'method': 'popup', 'minutes': 30},
                        ],
                    },
                }
                events.append(event_body)
                current_day_offset += weeks * 7
            else:
                days = parse_duration_to_days(duration_str)
                end_time = datetime.datetime.combine(start_date, datetime.time(11, 0)).isoformat()
                
                event_body = {
                    'summary': f"🎓 [Z-Mentor] {course.get('name')}",
                    'description': (
                        f"Lộ trình học tập cho mục tiêu: {request.career_goal}\n"
                        f"🔗 Link khóa học: {course.get('url')}\n"
                        f"⏱️ Thời lượng đề xuất: {duration_str} (Học 2h mỗi ngày trong {days} ngày)\n\n"
                        f"Được tạo tự động bởi Z-MentorAI."
                    ),
                    'start': {
                        'dateTime': start_time,
                        'timeZone': 'Asia/Ho_Chi_Minh',
                    },
                    'end': {
                        'dateTime': end_time,
                        'timeZone': 'Asia/Ho_Chi_Minh',
                    },
                    'recurrence': [
                        f'RRULE:FREQ=DAILY;COUNT={days}'
                    ],
                    'reminders': {
                        'useDefault': False,
                        'overrides': [
                            {'method': 'popup', 'minutes': 30},
                        ],
                    },
                }
                events.append(event_body)
                current_day_offset += days
                
        return {
            "career_goal": request.career_goal,
            "lacking_skills": request.lacking_skills,
            "events": events
        }
    except Exception as e:
        logger.exception("Failed to generate schedule")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate schedule: {str(e)}"
        )



# System prompt
def get_system_message(user_id: str) -> SystemMessage:
    import datetime
    current_date = datetime.date.today().strftime("%d/%m/%Y")
    return SystemMessage(content=(
        "You are the central Orchestrator Agent for a Job Orientation platform. Your ultimate goal is to guide users towards their ideal career. "
        "You are a dedicated career orientation assistant. You MUST decline any user queries or requests that are not related to the purpose of this chatbot (such as telling jokes, translating/summarizing unrelated general texts, solving math/general coding problems, or answering general knowledge questions). If a query is unrelated, politely refuse to answer, explaining in Vietnamese that your purpose is solely to assist with career scanning, Holland assessment, market scout, and academic roadmap building. "
        "You have access to three specialized agents as tools: Profile Scanner, Market Scout, and Academic Architect. "
        f"The current user's User ID (Google ID) is '{user_id}'. You must use this user ID string when calling tools. "
        "The Holland/RIASEC test is a Profile Scanner capability, not a separate agent. "
        "If the user asks for a Holland test, RIASEC test, personality-career test, career-interest test, or asks which career type fits them, call profile_scanner with task='holland_start'. "
        "When the user provides Holland answers, convert them into the required answers_json array and call profile_scanner with task='holland_score'. "
        "If the latest user message explicitly says to call profile_scanner with task='holland_score' and includes answers_json, call profile_scanner immediately and do not ask the user to reformat the answers. "
        "The MI / Multiple Intelligences assessment is a Profile Scanner capability for learning style and intelligence tendency, not an official MBTI test. "
        "If the user asks for MI, Multiple Intelligences, tri thong minh da dang, learning style, study style, MBTI, or personality-style testing, call profile_scanner with task='assessment_start' and assessment_type='multiple_intelligences'. "
        "When the user provides MI answers, convert them into answers_json and call profile_scanner with task='assessment_score' and assessment_type='multiple_intelligences'. "
        "If the latest user message explicitly says to call profile_scanner with task='assessment_score' and includes answers_json, call profile_scanner immediately and do not ask the user to reformat the answers. "
        "If the latest user message includes a cv_document_id from an uploaded CV, call profile_scanner with task='scan_profile' and pass that exact cv_document_id. "
        "If the user provides or changes a target role after uploading a CV, call profile_scanner with task='scan_profile' and target_role set to the user's exact role. Profile Scanner will select the user's latest CV when cv_document_id is unavailable. "
        "If the latest user message explicitly requests profile_confirm and includes cv_document_id plus decision, call profile_scanner immediately with task='profile_confirm', the exact cv_document_id, and decision. Do not reinterpret the decision. "
        "If the user asks whether their CV direction conflicts with Holland or MI, or asks for a combined career alignment analysis, call profile_scanner with task='career_alignment'. "
        "Career alignment is deterministic: never invent a conflict state or use MI as proof that a career is unsuitable. "
        "Do not invent CV analysis beyond Profile Scanner output; if the scanner says extraction is completed, explain that profile normalization and benchmark evaluation are the next steps. "
        "For ordinary CV/profile/background scanning, call profile_scanner with task='scan_profile'. "
        "For course roadmap or learning planning: "
        "If the user wants to build a learning plan or roadmap (e.g., clicks 'Dựng lộ trình học' or says 'Tôi muốn xây dựng lộ trình học tập') but has not specified their target job role or career goal, you MUST ask them what target position or career role they want to build the roadmap for first. Do not call any tool until they specify this target career goal. "
        "1. Once the target career_goal is known or specified, you MUST call the `academic_architect_input_verifier` tool with target career_goal, user_id, and action='verify' to load and show the target career goal and current skills to the user for validation. "
        "2. If `academic_architect_input_verifier` returns empty current_skills, stop and politely ask the user to upload their CV first before building a roadmap. "
        "3. If the user edits the skills (e.g. requests to add, remove, or modify skills, or types a message like 'thêm kỹ năng Python' or 'xóa kỹ năng Java'), calculate the new list of skills, then call `academic_architect_input_verifier` with action='update', user_id, career_goal, and the updated list of current_skills (as a comma-separated string) to update the backend database. Then explain the updated inputs. "
        "4. ONLY call the `academic_architect` tool with the user's target career_goal, user_id, and optionally current_skills once the user explicitly confirms (e.g., clicks the confirm button which sends 'Xác nhận và dựng lộ trình học tập', or says 'Đồng ý', 'Xác nhận', 'Confirm'). "
        f"Today's date is {current_date}. "
        "When calling academic_architect, you will receive the recommended courses and lacking skills metadata. You MUST write the detailed study roadmap in your final response in Vietnamese so it streams token-by-token to the user. "
        "Structure the roadmap with exactly these three sections:\n"
        "1. **Phân tích khoảng trống kỹ năng (Skill Gap Analysis)**: Highlight what skills the user has and what they need to acquire.\n"
        f"2. **Lộ trình học tập chi tiết (Detailed Study Roadmap)**: Organize the learning plan into clear steps/phases. Calculate and display exact start/end dates for each phase based on today's date ({current_date}), estimating workloads. For each course link you recommend, you MUST format it as a markdown link using its exact URL from the tool output, and append its duration/workload in parentheses (e.g. `[Tên Khóa Học](url) - 5 tuần (3-4 giờ/tuần)`). Only include the primary recommended course (labeled as 'Khóa học chính:') for each topic/phase, and do NOT list any alternative or reference courses (omit 'Khóa tham khảo thêm' sections entirely).\n"
        "3. **Lập lịch học**: Remind the user they can sync the primary recommended course directly to their Google Calendar using the button in the widget below.\n"
        "Based on the user's message, decide which tool(s) to call to gather the necessary information. "
        "Once you have the information, synthesize it and provide a helpful, coherent response to the user. "
        "If you need more information from the user before you can use a tool, ask them directly."
    ))

@app.post("/chat/stream")
async def chat_with_orchestrator_stream(request: ChatRequest, x_user_id: str = Header(...)):
    async def event_generator():
        try:
            session = await get_session_details(x_user_id, request.session_id)
            
            history_messages = build_history_messages(session)
            
            messages = [get_system_message(x_user_id)] + history_messages + [HumanMessage(content=request.message)]
            
            assistant_content = ""
            assistant_tool_calls = []
            running_tool_inputs = {}
            
            async for event in agent.astream_events({"messages": messages}, version="v2"):
                event_type = event["event"]
                name = event["name"]
                
                if event_type == "on_tool_start":
                    tool_input = event["data"].get("input")
                    running_tool_inputs[name] = tool_input
                    yield f"data: {json.dumps({'type': 'tool_start', 'tool': name, 'input': tool_input})}\n\n"
                
                elif event_type == "on_tool_end":
                    tool_output = event["data"].get("output")
                    serializable_output = serialize_tool_output(tool_output)
                    assistant_tool_calls.append({
                        "name": name,
                        "input": running_tool_inputs.get(name),
                        "output": serializable_output,
                        "status": "completed",
                    })
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
            await save_chat_exchange(
                x_user_id,
                request.session_id,
                request.message,
                assistant_content,
                assistant_tool_calls,
                request.attachment,
            )
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/chat", response_model=ChatResponse)
async def chat_with_orchestrator(request: ChatRequest, x_user_id: str = Header(...)):
    try:
        session = await get_session_details(x_user_id, request.session_id)
        
        history_messages = build_history_messages(session)
        
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
            
        await save_chat_exchange(
            x_user_id,
            request.session_id,
            request.message,
            final_response,
            user_attachment=request.attachment,
        )
        
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
