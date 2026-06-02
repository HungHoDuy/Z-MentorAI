import datetime
import hashlib
import json
import os
import re
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Profile Scanner Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STORAGE_ROOT = Path(os.getenv("PROFILE_SCANNER_LOCAL_STORAGE_DIR", ".local_storage")).resolve()
RESUME_STORAGE_DIR = STORAGE_ROOT / "resumes"
RESUME_DB_PATH = STORAGE_ROOT / "resumes_db.json"

SUPPORTED_RESUME_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
}

class ProfileRequest(BaseModel):
    user_id: str
    background_info: str

class ProfileResponse(BaseModel):
    status: str
    analysis: str

class ResumeUploadResponse(BaseModel):
    status: str
    resume_document_id: str
    user_id: str
    original_filename: str
    storage_provider: str
    storage_uri: str
    local_path: str
    mime_type: str
    file_kind: str
    file_size_bytes: int
    content_hash: str
    uploaded_at: str

def sanitize_path_part(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value or "").strip("-")
    return cleaned[:120] or fallback

def read_resume_db() -> dict:
    if not RESUME_DB_PATH.exists():
        return {"users": {}}
    try:
        return json.loads(RESUME_DB_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"users": {}}

def write_resume_db(db: dict) -> None:
    RESUME_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESUME_DB_PATH.write_text(json.dumps(db, indent=2), encoding="utf-8")

def store_resume_file(user_id: str, file: UploadFile) -> ResumeUploadResponse:
    mime_type = file.content_type or "application/octet-stream"
    if mime_type not in SUPPORTED_RESUME_TYPES:
        supported = ", ".join(sorted(SUPPORTED_RESUME_TYPES.keys()))
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported CV file type '{mime_type}'. Supported types: {supported}",
        )

    resume_document_id = str(uuid4())
    safe_user_id = sanitize_path_part(user_id, "anonymous")
    safe_filename = sanitize_path_part(file.filename or "resume", "resume")
    object_name = f"{resume_document_id}-{safe_filename}"
    target_dir = (RESUME_STORAGE_DIR / safe_user_id).resolve()
    target_path = (target_dir / object_name).resolve()

    if not str(target_path).startswith(str(RESUME_STORAGE_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid CV storage path.")

    target_dir.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    total_size = 0

    with target_path.open("wb") as output:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
            total_size += len(chunk)
            output.write(chunk)

    uploaded_at = datetime.datetime.utcnow().isoformat() + "Z"
    storage_uri = f"local://resumes/{safe_user_id}/{object_name}"

    response = ResumeUploadResponse(
        status="success",
        resume_document_id=resume_document_id,
        user_id=user_id,
        original_filename=safe_filename,
        storage_provider="local",
        storage_uri=storage_uri,
        local_path=str(target_path),
        mime_type=mime_type,
        file_kind=SUPPORTED_RESUME_TYPES[mime_type],
        file_size_bytes=total_size,
        content_hash=hasher.hexdigest(),
        uploaded_at=uploaded_at,
    )

    db = read_resume_db()
    user_data = db["users"].setdefault(user_id, {"resumes": []})
    response_data = response.model_dump() if hasattr(response, "model_dump") else response.dict()
    user_data["resumes"].append(response_data)
    write_resume_db(db)

    return response

@app.post("/scan", response_model=ProfileResponse)
async def scan_profile(request: ProfileRequest):
    # Placeholder for actual LangChain agent logic
    # Here you would initialize your LangChain agent and process the background info
    
    analysis_result = f"Mocked profile analysis for user {request.user_id} with background: {request.background_info}. Found key strengths in technical skills."
    
    return ProfileResponse(
        status="success",
        analysis=analysis_result
    )

@app.post("/resumes/upload", response_model=ResumeUploadResponse)
async def upload_resume(file: UploadFile = File(...), x_user_id: str = Header(...)):
    return store_resume_file(x_user_id, file)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "profile_scanner"}
