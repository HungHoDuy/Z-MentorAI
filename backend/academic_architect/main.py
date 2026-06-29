import os
import sys
import time
import json
import logging
import uuid
import datetime
from typing import Any, Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"Academic Architect: Loaded environment from {env_path}")
else:
    print("Academic Architect: Warning, no .env file found.")

from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from langchain_google_vertexai import VertexAIEmbeddings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("academic_architect")

COLLECTION_NAME = "learning_material"

# Initialize LLM
llm = None
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
USE_FIRESTORE = os.getenv("USE_FIRESTORE", "false").lower() == "true"

if USE_VERTEX_AI:
    from langchain_google_vertexai import ChatVertexAI
    llm = ChatVertexAI(
        model_name="gemini-2.5-flash",
        location="asia-southeast1",
        temperature=0.7
    )
    logger.info("Academic Architect: Using Vertex AI gemini-2.5-flash")
elif GEMINI_API_KEY:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
    logger.info("Academic Architect: Using ChatGoogleGenerativeAI with API Key")
else:
    logger.warning("Academic Architect: Neither Vertex AI nor GEMINI_API_KEY is configured for LLM.")

app = FastAPI(title="Academic Architect Agent")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    search_text: str
    search_mode: str  # "name" or "description"
    domain: Optional[str] = None
    k: Optional[int] = 3

class SearchResponse(BaseModel):
    feature: str = "course_search"
    search_text: str
    search_mode: str
    domain: Optional[str]
    query_time_ms: float
    courses: list[dict]

import re

class SkillsUpdateRequest(BaseModel):
    skills: List[str]

class ArchitectRequest(BaseModel):
    career_goal: str
    current_skills: str
    user_id: Optional[str] = None

class ArchitectResponse(BaseModel):
    status: str
    academic_plan: str
    courses: Optional[List[dict]] = None
    alternative_courses: Optional[List[dict]] = None
    lacking_skills: Optional[List[str]] = None
    matched_jobs: Optional[List[dict]] = None
    career_goal: Optional[str] = None

def get_firestore_client():
    db_name = os.getenv("FIRESTORE_DATABASE")
    if db_name and db_name != "(default)":
        return firestore.Client(database=db_name)
    return firestore.Client()

LOCAL_SKILLS_DB_PATH = Path(__file__).resolve().parent / "user_skills_db.json"

def read_local_skills_db() -> dict:
    if not LOCAL_SKILLS_DB_PATH.exists():
        return {}
    try:
        with open(LOCAL_SKILLS_DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def write_local_skills_db(db_data: dict):
    try:
        with open(LOCAL_SKILLS_DB_PATH, "w", encoding="utf-8") as f:
            json.dump(db_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to write local skills db: {e}")

def load_jobs() -> List[dict]:
    jobs_path = Path(__file__).resolve().parent / "first_page_jobs.json"
    if not jobs_path.exists():
        logger.warning(f"Jobs file not found at {jobs_path}")
        return []
    try:
        with open(jobs_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading jobs file: {e}")
        return []

# Cache for embeddings instances
_embeddings_cache = {}

def get_embeddings(dimensions: Optional[int] = None):
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("PROJECT_ID")
    location = os.getenv("VERTEX_AI_LOCATION", "asia-southeast1")
    cache_key = (dimensions, project, location)
    if cache_key not in _embeddings_cache:
        kwargs = {
            "model_name": "text-embedding-004",
        }
        if dimensions is not None:
            kwargs["dimensions"] = dimensions
        if project:
            kwargs["project"] = project
        if location:
            kwargs["location"] = location
        logger.info(f"Academic Architect: Initializing VertexAIEmbeddings with params {kwargs}")
        _embeddings_cache[cache_key] = VertexAIEmbeddings(**kwargs)
    return _embeddings_cache[cache_key]

def perform_vector_search(search_text: str, search_mode: str, domain: Optional[str] = None, k: int = 3) -> tuple[List[dict], str]:
    """Helper to perform native Firestore vector search using find_nearest with domain pre-filtering."""
    normalized_mode = search_mode.strip().lower()
    if normalized_mode not in ("name", "description"):
        raise ValueError("search_mode must be 'name' or 'description'")
        
    # 1. Embed query
    if normalized_mode == "name":
        # 128 dimensions for name embedding
        embeddings = get_embeddings(dimensions=128)
        vector_field = "name_embedding"
    else:
        # Default 768 dimensions for description embedding
        embeddings = get_embeddings(dimensions=None)
        vector_field = "description_embedding"
        
    query_vector = embeddings.embed_query(search_text)
    
    # 2. Connect to Firestore
    db = get_firestore_client()
    col_ref = db.collection(COLLECTION_NAME)
    
    # Validate and fallback domain if needed
    valid_domains = {
        "business", "computer-science", "information-technology", "data-science", 
        "life-sciences", "physical-science-and-engineering", "personal-development", 
        "social-sciences", "arts-and-humanities", "math-and-logic", "language-learning"
    }
    
    norm_domain = domain.strip().lower() if domain else ""
    if norm_domain not in valid_domains:
        logger.warning(f"Invalid or missing domain '{domain}'. Defaulting to 'computer-science'.")
        norm_domain = "computer-science"
        
    # 3. Build Vector query (always filtering by domain)
    query = col_ref.where("domainIDs", "array_contains", norm_domain).find_nearest(
        vector_field=vector_field,
        query_vector=Vector(query_vector),
        distance_measure=DistanceMeasure.COSINE,
        limit=k,
        distance_result_field="vector_distance"
    )
    
    # 4. Stream and map results
    t_firestore_start = time.perf_counter()
    docs = list(query.stream())
    t_firestore_elapsed = (time.perf_counter() - t_firestore_start) * 1000
    logger.info(f"Firestore find_nearest query took {t_firestore_elapsed:.2f} ms")
    results = []
    for doc in docs:
        doc_data = doc.to_dict()
        
        # similarity = 1.0 - cosine_distance
        dist = doc_data.get("vector_distance")
        score = 1.0 - float(dist) if dist is not None else 0.0
        
        # Extract or default duration
        duration_val = doc_data.get("duration")
        if not duration_val:
            desc_lower = (doc_data.get("description") or "").lower()
            name_lower = (doc_data.get("name") or "").lower()
            text_to_search = name_lower + " " + desc_lower
            
            # Simple regex to extract hours if present
            match = re.search(r'(\d+)\s*(hour|hr|giờ|hour|hrs)', text_to_search)
            if match:
                duration_val = f"{match.group(1)} giờ"
            else:
                certs_list = doc_data.get("certificates") or []
                if any("specialization" in str(c).lower() for c in certs_list):
                    duration_val = "3 tháng"
                elif any("professional" in str(c).lower() for c in certs_list):
                    duration_val = "6 tháng"
                else:
                    duration_val = "15 giờ"

        course = {
            "course_id": doc_data.get("course_id") or doc.id,
            "name": doc_data.get("name") or "",
            "description": doc_data.get("description") or "",
            "slug": doc_data.get("slug") or "",
            "course_type": doc_data.get("course_type") or "",
            "certificates": doc_data.get("certificates") or [],
            "domain_types": doc_data.get("domain_types") or [],
            "partners": doc_data.get("partners") or [],
            "photo_url": doc_data.get("photo_url") or "",
            "score": score,
            "duration": duration_val,
            "workload": doc_data.get("workload") or ""
        }
        
        # Build Coursera URL
        slug = course.get("slug")
        certs = course.get("certificates") or []
        is_spec = any("specialization" in str(c).lower() for c in certs)
        if is_spec:
            course["url"] = f"https://www.coursera.org/specializations/{slug}"
        else:
            course["url"] = f"https://www.coursera.org/learn/{slug}"
            
        results.append(course)
        
    return results, norm_domain

@app.post("/search", response_model=SearchResponse)
async def search_courses(request: SearchRequest):
    """Rest endpoint to perform RAG searching directly on the Coursera catalog."""
    start_time = time.perf_counter()
    try:
        results, domain_used = perform_vector_search(
            search_text=request.search_text,
            search_mode=request.search_mode,
            domain=request.domain,
            k=request.k or 5
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Error in /search API")
        raise HTTPException(status_code=500, detail=str(e))
        
    query_time_ms = (time.perf_counter() - start_time) * 1000
    
    return SearchResponse(
        search_text=request.search_text,
        search_mode=request.search_mode,
        domain=domain_used,
        query_time_ms=query_time_ms,
        courses=results
    )

@app.post("/architect", response_model=ArchitectResponse)
async def create_plan(request: ArchitectRequest):
    """Generate roadmap by identifying skills gaps and querying Coursera database."""
    # 1. Retrieve user's current skills from Firestore if user_id is provided
    user_skills = []
    if request.user_id:
        if USE_FIRESTORE:
            try:
                db = get_firestore_client()
                cv_docs_query = db.collection("profile_scanner_cv_documents").where("user_id", "==", request.user_id).stream()
                cv_docs = list(cv_docs_query)
                if cv_docs:
                    cv_docs.sort(key=lambda d: d.to_dict().get("analyzed_at", d.to_dict().get("extracted_at", "")), reverse=True)
                    latest_doc = cv_docs[0].to_dict()
                    profile_analysis = latest_doc.get("profile_analysis", {})
                    user_skills = profile_analysis.get("extracted_skills", []) or latest_doc.get("extracted_skills", [])
                    if not user_skills:
                        user_skills = profile_analysis.get("structured_profile", {}).get("skills", [])
                    logger.info(f"Retrieved user skills from Firestore for user {request.user_id}: {user_skills}")
            except Exception as ex:
                logger.error(f"Failed to query user CV documents from Firestore: {ex}")
        
        # Fallback to local DB if no skills found in Firestore or Firestore disabled
        if not user_skills:
            local_db = read_local_skills_db()
            user_skills = local_db.get(request.user_id, [])
            if user_skills:
                logger.info(f"Retrieved user skills from local DB for user {request.user_id}: {user_skills}")

    # Fallback to current_skills if no skills found in CV document
    if not user_skills and request.current_skills:
        user_skills = [s.strip() for s in request.current_skills.split(",") if s.strip()]

    if not llm:
        mock_plan = f"Lộ trình đề xuất để chuyển đổi từ '{user_skills}' sang '{request.career_goal}'."
        return ArchitectResponse(
            status="success",
            academic_plan=mock_plan,
            courses=[],
            lacking_skills=[],
            matched_jobs=[],
            career_goal=request.career_goal
        )
        
    try:
        # 2. Match jobs in first_page_jobs.json and filter top candidates
        candidate_jobs = []
        goal_lower = request.career_goal.lower()
        goal_keywords = [w for w in re.split(r'\W+', goal_lower) if len(w) > 2]
        
        all_jobs = load_jobs()
        for job in all_jobs:
            title = (job.get("job_title") or "").lower()
            url = (job.get("job_url") or "").lower()
            description = (job.get("Mô tả Công việc") or "").lower()
            requirements = (job.get("Yêu Cầu Công Việc") or "").lower()
            industry = (job.get("Ngành nghề") or "").lower()
            
            url_title = ""
            if "/" in url:
                slug = url.split("/")[-1]
                if "." in slug:
                    url_title = slug.split(".")[0].replace("-", " ")
                    
            text_to_search = f"{title} {url_title} {industry} {description} {requirements}"
            
            score = 0
            if goal_lower in title or goal_lower in url_title:
                score += 10
            if goal_lower in industry:
                score += 5
            for kw in goal_keywords:
                if kw in title or kw in url_title:
                    score += 4
                if kw in industry:
                    score += 2
                if kw in requirements:
                    score += 1
                    
            if score > 0:
                candidate_jobs.append((score, job))

        candidate_jobs.sort(key=lambda x: x[0], reverse=True)
        top_candidates = [item[1] for item in candidate_jobs[:5]]
        if not top_candidates:
            top_candidates = all_jobs[:5]

        # 3. LLM analyzes gaps and identifies search queries
        jobs_context = ""
        for idx, job in enumerate(top_candidates):
            title = job.get("job_title") or ""
            url = job.get("job_url") or ""
            company = job.get("company") or "Công ty tuyển dụng"
            salary = job.get("Lương") or "Thỏa thuận"
            reqs = job.get("Yêu Cầu Công Việc") or ""
            desc = job.get("Mô tả Công việc") or ""
            
            url_title = ""
            if "/" in url:
                slug = url.split("/")[-1]
                if "." in slug:
                    url_title = slug.split(".")[0].replace("-", " ").title()
            
            display_title = title if not title.startswith("Job ") else (url_title or title)
            jobs_context += f"Job Index: {idx}\nTitle: {display_title}\nCompany: {company}\nSalary: {salary}\nRequirements: {reqs[:400]}\nDescription: {desc[:400]}\nURL: {url}\n\n"

        prompt_queries = f"""
You are the AI Academic Architect.
The user wants to transition to the target career goal. We have retrieved a list of relevant job postings from our market database.
Target Career Goal: "{request.career_goal}"
User's Current Skills: {json.dumps(user_skills)}

Here are the candidate jobs:
{jobs_context}

Step 1: Identify 1 to 3 job postings that best match the career goal (by Job Index).
Step 2: Extract the required skills (target skills) for these matched jobs.
Step 3: Perform a skill gap analysis by comparing target skills with the user's current skills. Identify the specific skills the user is lacking.
Step 4: For each lacking skill, formulate a single search query to look up courses in our Coursera catalog, and specify the domain.
Always specify a domain from one of these 11 categories:
"business", "computer-science", "information-technology", "data-science", "life-sciences", "physical-science-and-engineering", "personal-development", "social-sciences", "arts-and-humanities", "math-and-logic", "language-learning"

Return the output as a valid JSON object with these keys (do not add any markdown formatting wrapper, extra text, or prefix outside the JSON):
- "matched_jobs": list of objects containing "job_id", "job_title", "company", "url" for the best matched jobs from the candidates above. Use clean titles (if the original title starts with "Job ", use the descriptive title from the URL slug).
- "lacking_skills": list of strings of specific skills/technologies the user lacks.
- "search_queries": list of objects for Coursera search, each containing:
  - "subject": the name of the lacking skill/subject
  - "search_text": the search query string
  - "search_mode": "name" or "description"
  - "domain": the domain name from the 11 strings above

Example response:
{{
  "matched_jobs": [
    {{"job_id": "35C73750", "job_title": "Kỹ sư Shop drawing", "company": "Handong", "url": "https://..."}}
  ],
  "lacking_skills": ["Revit", "AutoCAD"],
  "search_queries": [
    {{"subject": "Revit", "search_text": "revit architecture bim design", "search_mode": "description", "domain": "physical-science-and-engineering"}},
    {{"subject": "AutoCAD", "search_text": "autocad 2d drafting introduction", "search_mode": "name", "domain": "physical-science-and-engineering"}}
  ]
}}
"""
        res_queries = await llm.ainvoke(prompt_queries)
        raw_content = res_queries.content.strip()
        
        # Clean any markdown JSON wrapper code blocks
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
        raw_content = raw_content.strip()
        
        try:
            analysis_data = json.loads(raw_content)
        except Exception:
            logger.warning(f"Failed to parse LLM analysis JSON: {raw_content}. Falling back to default search queries.")
            analysis_data = {
                "matched_jobs": [{"job_id": j.get("job_id"), "job_title": j.get("job_title"), "company": j.get("company"), "url": j.get("job_url")} for j in top_candidates[:2]],
                "lacking_skills": ["General Skills"],
                "search_queries": [{"subject": "Goal", "search_text": request.career_goal, "search_mode": "description", "domain": "computer-science"}]
            }
            
        matched_jobs = analysis_data.get("matched_jobs", [])
        lacking_skills = analysis_data.get("lacking_skills", [])
        query_tasks = analysis_data.get("search_queries", [])

        # 4. Perform vector search for each identified query in parallel
        import asyncio
        retrieved_courses = []
        seen_course_ids = set()

        async def run_search(task):
            s_text = task.get("search_text")
            s_mode = task.get("search_mode", "description")
            s_domain = task.get("domain")
            if not s_text:
                return []
            try:
                # perform_vector_search is synchronous, run it in a thread pool
                results, domain_used = await asyncio.to_thread(
                    perform_vector_search, s_text, s_mode, s_domain, 3
                )
                return results
            except Exception as ex:
                logger.error(f"Failed to run vector query for task '{s_text}': {ex}")
                return []

        search_tasks = [run_search(task) for task in query_tasks]
        results_list = await asyncio.gather(*search_tasks)

        for results in results_list:
            for c in results:
                if c["course_id"] not in seen_course_ids:
                    seen_course_ids.add(c["course_id"])
                    retrieved_courses.append(c)

        # 5. Let LLM select the single best course from the retrieved courses
        best_course = retrieved_courses[0] if retrieved_courses else None
        if len(retrieved_courses) > 1:
            courses_list_text = "\n".join([f"Index {idx}: {c['name']} (Mô tả: {c['description'][:200]})" for idx, c in enumerate(retrieved_courses)])
            prompt_select_best = f"""
Dựa trên mục tiêu nghề nghiệp: "{request.career_goal}" và các kỹ năng còn thiếu: {json.dumps(lacking_skills)}.
Hãy chọn ra đúng 1 khóa học phù hợp nhất, thiết thực nhất từ danh sách các khóa học Coursera dưới đây để người học bắt đầu ngay lập tức.
Trả về duy nhất chỉ số Index của khóa học được chọn (ví dụ: 0 hoặc 1 hoặc 2), không trả thêm bất kỳ từ ngữ nào khác.

Danh sách khóa học:
{courses_list_text}
"""
            try:
                res_best = await llm.ainvoke(prompt_select_best)
                best_idx_str = res_best.content.strip()
                match = re.search(r'\d+', best_idx_str)
                if match:
                    best_idx = int(match.group(0))
                    if 0 <= best_idx < len(retrieved_courses):
                        best_course = retrieved_courses[best_idx]
                        logger.info(f"LLM selected best course before plan: index {best_idx} ({best_course['name']})")
            except Exception as e:
                logger.error(f"Failed to let LLM select best course: {e}")

        selected_courses = [best_course] if best_course else []
        alternative_courses = [c for c in retrieved_courses if c["course_id"] != (best_course["course_id"] if best_course else "")]
        
        # We delegate academic_plan generation to the orchestrator for streaming token-by-token.
        academic_plan_summary = f"Lộ trình học tập đề xuất cho mục tiêu {request.career_goal}."

        return ArchitectResponse(
            status="success",
            academic_plan=academic_plan_summary,
            courses=selected_courses,
            alternative_courses=alternative_courses,
            lacking_skills=lacking_skills,
            matched_jobs=matched_jobs,
            career_goal=request.career_goal
        )
    except Exception as e:
        logger.exception("Error during academic plan generation")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/skills/{user_id}")
async def get_user_skills(user_id: str):
    user_skills = []
    # 1. Try Firestore if enabled
    if USE_FIRESTORE:
        try:
            db = get_firestore_client()
            cv_docs_query = db.collection("profile_scanner_cv_documents").where("user_id", "==", user_id).stream()
            cv_docs = list(cv_docs_query)
            if cv_docs:
                cv_docs.sort(key=lambda d: d.to_dict().get("analyzed_at", d.to_dict().get("extracted_at", "")), reverse=True)
                latest_doc = cv_docs[0].to_dict()
                profile_analysis = latest_doc.get("profile_analysis", {})
                user_skills = profile_analysis.get("extracted_skills", []) or latest_doc.get("extracted_skills", [])
                if not user_skills:
                    user_skills = profile_analysis.get("structured_profile", {}).get("skills", [])
        except Exception as e:
            logger.error(f"Failed to get user skills from Firestore: {e}")
            
    # 2. Try local DB fallback (or if Firestore returned nothing)
    if not user_skills:
        local_db = read_local_skills_db()
        user_skills = local_db.get(user_id, [])
        
    return {"skills": user_skills}

@app.post("/skills/{user_id}")
async def update_user_skills(user_id: str, request: SkillsUpdateRequest):
    # 1. Update Firestore if enabled
    updated_firestore = False
    if USE_FIRESTORE:
        try:
            db = get_firestore_client()
            cv_docs_query = db.collection("profile_scanner_cv_documents").where("user_id", "==", user_id).stream()
            cv_docs = list(cv_docs_query)
            
            if cv_docs:
                cv_docs.sort(key=lambda d: d.to_dict().get("analyzed_at", d.to_dict().get("extracted_at", "")), reverse=True)
                latest_doc_ref = cv_docs[0].reference
                latest_doc = cv_docs[0].to_dict()
                
                # Update standard locations
                updates = {
                    "extracted_skills": request.skills,
                    "analyzed_at": datetime.datetime.utcnow().isoformat() + "Z"
                }
                
                # Also nested locations
                if "profile_analysis" in latest_doc:
                    profile_analysis = latest_doc["profile_analysis"] or {}
                    profile_analysis["extracted_skills"] = request.skills
                    if "structured_profile" in profile_analysis:
                        structured_profile = profile_analysis["structured_profile"] or {}
                        structured_profile["skills"] = request.skills
                        profile_analysis["structured_profile"] = structured_profile
                    updates["profile_analysis"] = profile_analysis
                    
                latest_doc_ref.update(updates)
                logger.info(f"Updated user skills in Firestore for user {user_id} in doc {latest_doc_ref.id}")
                updated_firestore = True
        except Exception as e:
            logger.error(f"Failed to update user skills in Firestore: {e}")
            raise HTTPException(status_code=500, detail=str(e))
            
    # 2. Update local DB
    try:
        local_db = read_local_skills_db()
        local_db[user_id] = request.skills
        write_local_skills_db(local_db)
        logger.info(f"Updated user skills in local DB for user {user_id}: {request.skills}")
    except Exception as e:
        logger.error(f"Failed to update user skills in local DB: {e}")
        if not updated_firestore:
            raise HTTPException(status_code=500, detail=str(e))
            
    return {"status": "success", "skills": request.skills}

@app.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "service": "academic_architect"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080)
