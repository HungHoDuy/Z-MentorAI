import os
import sys
import time
import json
import logging
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
    k: Optional[int] = 5

class SearchResponse(BaseModel):
    feature: str = "course_search"
    search_text: str
    search_mode: str
    domain: Optional[str]
    query_time_ms: float
    courses: list[dict]

class ArchitectRequest(BaseModel):
    career_goal: str
    current_skills: str

class ArchitectResponse(BaseModel):
    status: str
    academic_plan: str
    courses: Optional[List[dict]] = None

def get_firestore_client():
    db_name = os.getenv("FIRESTORE_DATABASE")
    if db_name and db_name != "(default)":
        return firestore.Client(database=db_name)
    return firestore.Client()

def perform_vector_search(search_text: str, search_mode: str, domain: Optional[str] = None, k: int = 5) -> tuple[List[dict], str]:
    """Helper to perform native Firestore vector search using find_nearest with domain pre-filtering."""
    normalized_mode = search_mode.strip().lower()
    if normalized_mode not in ("name", "description"):
        raise ValueError("search_mode must be 'name' or 'description'")
        
    # 1. Embed query
    if normalized_mode == "name":
        # 128 dimensions for name embedding
        embeddings = VertexAIEmbeddings(model_name="text-embedding-004", dimensions=128)
        vector_field = "name_embedding"
    else:
        # Default 768 dimensions for description embedding
        embeddings = VertexAIEmbeddings(model_name="text-embedding-004")
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
            "score": score
        }
        
        # Build Coursera URL
        slug = course.get("slug")
        certs = course.get("certificates") or []
        is_spec = "Specialization" in certs
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
    if not llm:
        mock_plan = f"Lộ trình đề xuất để chuyển đổi từ '{request.current_skills}' sang '{request.career_goal}'."
        return ArchitectResponse(
            status="success",
            academic_plan=mock_plan,
            courses=[]
        )
        
    try:
        # Step 1: LLM analyzes gaps and identifies search queries
        prompt_queries = f"""
You are the AI Academic Architect.
The user wants to transition from their current skills to a target career goal.
Current Skills: "{request.current_skills}"
Career Goal: "{request.career_goal}"

Identify 2 to 3 main skill gaps/subjects that the user needs to learn.
For each subject, formulate a single search query to look up courses in our Coursera catalog.
Specify the search mode: "name" (for specific course title keywords) or "description" (for conceptual topics).
Always specify a domain from one of these 11 categories (it is required, do not output null or any other domain not listed here):
"business", "computer-science", "information-technology", "data-science", "life-sciences", "physical-science-and-engineering", "personal-development", "social-sciences", "arts-and-humanities", "math-and-logic", "language-learning"

Return the output as a valid JSON array of objects, with no markdown styling, no quotes outside the JSON, and no extra text.
Each object must have these keys:
- "subject": brief name of the subject
- "search_text": the search query
- "search_mode": "name" or "description"
- "domain": the domain name (must be one of the 11 strings above)

Example:
[
  {{"subject": "Docker", "search_text": "docker containerization and kubernetes", "search_mode": "description", "domain": "computer-science"}},
  {{"subject": "Python Basics", "search_text": "python programming introduction", "search_mode": "name", "domain": "computer-science"}}
]
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
            query_tasks = json.loads(raw_content)
        except Exception:
            logger.warning(f"Failed to parse LLM search queries JSON: {raw_content}. Falling back to career goal.")
            query_tasks = [{"subject": "Goal", "search_text": request.career_goal, "search_mode": "description", "domain": "computer-science"}]
            
        # Step 2: Perform vector search for each identified query
        retrieved_courses = []
        seen_course_ids = set()
        
        for task in query_tasks:
            s_text = task.get("search_text")
            s_mode = task.get("search_mode", "description")
            s_domain = task.get("domain")
            
            if s_text:
                try:
                    results, domain_used = perform_vector_search(search_text=s_text, search_mode=s_mode, domain=s_domain, k=3)
                    for c in results:
                        if c["course_id"] not in seen_course_ids:
                            seen_course_ids.add(c["course_id"])
                            retrieved_courses.append(c)
                except Exception as ex:
                    logger.error(f"Failed to run vector query for task '{s_text}': {ex}")
                    
        # Step 3: Format course metadata for LLM plan generation context
        courses_context = ""
        for idx, c in enumerate(retrieved_courses):
            partners = ", ".join([p.get("name") if isinstance(p, dict) else str(p) for p in c.get("partners") or []])
            certs = ", ".join(c.get("certificates") or [])
            courses_context += f"[{idx+1}] Tên: {c['name']} | Đối tác: {partners} | Chứng chỉ: {certs} | Loại: {c['course_type']}\nMô tả: {c['description'][:200]}...\n\n"
            
        # Step 4: Generate roadmap using the retrieved courses
        prompt_roadmap = f"""
You are the AI Academic Architect, a professional career guidance counselor and learning designer.
The user wants to transition from their current skills to a target career goal.
Current Skills: "{request.current_skills}"
Career Goal: "{request.career_goal}"

We have found the following relevant courses in our database:
{courses_context}

Create a personalized, professional, and visually appealing academic roadmap in markdown format.
Structure the roadmap with clear steps or phases (e.g., Phase 1: Fundamentals, Phase 2: Core Skills, Phase 3: Specialization/Advanced).
For each phase:
- Explain what skills the user will acquire.
- Explicitly recommend 1 or 2 courses from the provided list (refer to them by their exact titles). Include the provider/partner.
- Keep the tone encouraging, structured, and goal-oriented.
"""
        res_roadmap = await llm.ainvoke(prompt_roadmap)
        roadmap_content = res_roadmap.content.strip()
        
        return ArchitectResponse(
            status="success",
            academic_plan=roadmap_content,
            courses=retrieved_courses[:5] # Limit output to top 5 recommendations
        )
        
    except Exception as e:
        logger.exception("Error during academic plan generation")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {
        "status": "ok", 
        "service": "academic_architect"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080)
