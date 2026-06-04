import os
import re
import json
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Import CourseSearchTool handling both local execution and Docker imports
try:
    from course_search_tool import CourseSearchTool
except ImportError:
    from backend.academic_architect.course_search_tool import CourseSearchTool

app = FastAPI(title="Academic Architect Agent")

class ArchitectRequest(BaseModel):
    career_goal: str
    current_skills: str

class ArchitectResponse(BaseModel):
    status: str
    academic_plan: str

# Setup the LLM
USE_VERTEX_AI = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
llm = None

if USE_VERTEX_AI:
    try:
        from langchain_google_vertexai import ChatVertexAI
        llm = ChatVertexAI(
            model_name="gemini-2.5-flash",
            location="asia-southeast1",
            temperature=0.7
        )
        print("Using Vertex AI model gemini-2.5-flash in region asia-southeast1")
    except Exception as e:
        print(f"Failed to initialize Vertex AI: {e}. Falling back to Gemini API Key.")

if llm is None:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.7)
    print("Using Gemini API Key-based ChatGoogleGenerativeAI")

searcher = CourseSearchTool()

def clean_json_text(text: str) -> str:
    """Cleans up markdown code blocks if the LLM wraps JSON response."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text)
    return text.strip()

@app.post("/architect", response_model=ArchitectResponse)
async def create_plan(request: ArchitectRequest):
    try:
        # Step 1: Identify skills gap
        gap_prompt = (
            f"You are an expert career counselor. The user wants to transition from their current skills: "
            f"'{request.current_skills}' to achieve the career goal: '{request.career_goal}'.\n"
            f"Identify the top 3 most critical specific skills or technical topics they need to learn to bridge this gap.\n"
            f"Provide your response in JSON format as a list of strings.\n"
            f"Example response format:\n"
            f'["Machine Learning", "System Design", "Docker"]\n'
            f"Do not include any explanation or markdown formatting, just return the raw JSON array."
        )
        
        gap_res = await llm.ainvoke(gap_prompt)
        cleaned_json = clean_json_text(gap_res.content)
        
        try:
            target_skills = json.loads(cleaned_json)
            if not isinstance(target_skills, list):
                target_skills = [request.career_goal]
        except Exception as parse_err:
            print(f"Failed to parse target skills JSON: {parse_err}. LLM Response: {gap_res.content}")
            # Fallback to general career goal and a default query
            target_skills = [request.career_goal]
        
        # Step 2: Search for courses in parallel for each skill
        search_tasks = [searcher.search_all(skill) for skill in target_skills]
        search_results = await asyncio.gather(*search_tasks)
        
        # Consolidate course results
        courses_by_skill = {}
        for skill, result in zip(target_skills, search_results):
            courses_by_skill[skill] = result
            
        # Step 3: Generate detailed academic roadmap containing the actual courses
        roadmap_prompt = (
            f"You are an expert academic advisor. Create a personalized learning roadmap to transition from:\n"
            f"Current Skills: '{request.current_skills}'\n"
            f"To Career Goal: '{request.career_goal}'\n\n"
            f"Here are real courses we found on Coursera, Udemy, and YouTube for the target skills:\n"
            f"{json.dumps(courses_by_skill, indent=2)}\n\n"
            f"Write a comprehensive, step-by-step roadmap. For each phase or skill, suggest specific courses from the provided list, "
            f"making sure to include their exact clickable Markdown links (e.g. [Course Title](URL) on Platform).\n"
            f"Also, provide brief recommendations on how they should approach learning these topics.\n"
            f"Make sure the response is beautifully formatted in Markdown."
        )
        
        roadmap_res = await llm.ainvoke(roadmap_prompt)
        
        return ArchitectResponse(
            status="success",
            academic_plan=roadmap_res.content
        )
        
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "academic_architect"}
