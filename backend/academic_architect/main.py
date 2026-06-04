import os
import re
import json
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

import httpx

VM_SERVER_URL = os.getenv("VM_SERVER_URL", "http://localhost:8080")


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

async def search_courses_via_vm(query: str) -> dict:
    url = f"{VM_SERVER_URL.rstrip('/')}/search"
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json={"query": query})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error querying VM server for query '{query}': {e}")
            # Fallback to empty results to prevent crashing the entire pipeline
            return {"coursera": [], "edx": [], "youtube": []}

async def filter_and_align_courses(courses_dict: dict, target_skill: str, career_goal: str) -> dict:
    """Uses the LLM to post-process, filter, and rank the crawled Coursera, edX, and YouTube results.
    It evaluates whether each course aligns with the user's career goal and target skill,
    and returns the top 3-4 most relevant courses per platform.
    """
    flat_list = []
    for platform, items in courses_dict.items():
        for item in items:
            flat_list.append(item)
            
    if not flat_list:
        return {"coursera": [], "edx": [], "youtube": []}
        
    prompt = (
        f"You are an expert curriculum builder. A user wants to transition to the career goal '{career_goal}' "
        f"and needs to learn the specific target skill '{target_skill}'.\n"
        f"We crawled 10 courses/videos from Coursera, edX, and YouTube for this skill:\n"
        f"{json.dumps(flat_list, indent=2)}\n\n"
        f"Evaluate each course/video carefully based on the following criteria:\n"
        f"1. Does it directly align with learning '{target_skill}' for a '{career_goal}' role?\n"
        f"2. Is it a high-quality educational resource (e.g. reputable university/creator or high views/rating)?\n"
        f"Select the top 3-4 most relevant courses/videos total (balancing across platforms if possible). Filter out duplicates or irrelevant results.\n"
        f"Provide your response in JSON format as a dictionary where the keys are platforms ('coursera', 'edx', 'youtube') "
        f"and the values are lists of the selected course dictionaries (preserving 'title', 'url', 'platform', 'partner_creator', 'rating', and 'duration_details').\n"
        f"Do not include any explanation or markdown formatting, just return the raw JSON object."
    )
    
    try:
        res = await llm.ainvoke(prompt)
        cleaned_json = clean_json_text(res.content)
        filtered = json.loads(cleaned_json)
        if isinstance(filtered, dict):
            for key in ["coursera", "edx", "youtube"]:
                if key not in filtered:
                    filtered[key] = []
            return filtered
    except Exception as e:
        print(f"Error in course post-processing/filtering: {e}")
        
    return {
        "coursera": courses_dict.get("coursera", [])[:3],
        "edx": courses_dict.get("edx", [])[:3],
        "youtube": courses_dict.get("youtube", [])[:3]
    }

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
            target_skills = [request.career_goal]
        
        # Step 2: Search for courses in parallel for each skill (retrieving 10 items per site)
        search_tasks = [search_courses_via_vm(skill) for skill in target_skills]
        search_results = await asyncio.gather(*search_tasks)
        
        # Step 3: Post-process and filter search results for alignment
        filter_tasks = [
            filter_and_align_courses(res, skill, request.career_goal)
            for skill, res in zip(target_skills, search_results)
        ]
        filtered_results = await asyncio.gather(*filter_tasks)
        
        # Consolidate course results
        courses_by_skill = {}
        for skill, result in zip(target_skills, filtered_results):
            courses_by_skill[skill] = result
            
        # Step 4: Generate detailed academic roadmap containing the actual courses
        roadmap_prompt = (
            f"You are an expert academic advisor. Create a personalized learning roadmap to transition from:\n"
            f"Current Skills: '{request.current_skills}'\n"
            f"To Career Goal: '{request.career_goal}'\n\n"
            f"Here are real, post-processed courses we found on Coursera, edX, and YouTube that align with the target skills:\n"
            f"{json.dumps(courses_by_skill, indent=2)}\n\n"
            f"Write a comprehensive, step-by-step roadmap. For each phase or skill, suggest specific courses from the provided list, "
            f"making sure to include their exact clickable Markdown links (e.g. [Course Title](URL) on Platform).\n"
            f"IMPORTANT: If the course lists for a skill are empty or missing results for Coursera or edX (due to temporary rate-limiting), "
            f"you must suggest highly reputable, real courses from your own knowledge base for that skill. "
            f"Ensure any self-suggested courses have valid, realistic URLs (e.g., https://www.coursera.org/learn/course-slug or https://www.edx.org/learn/course-slug).\n"
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
