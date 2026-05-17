from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Academic Architect Agent")

class ArchitectRequest(BaseModel):
    career_goal: str
    current_skills: str

class ArchitectResponse(BaseModel):
    status: str
    academic_plan: str

@app.post("/architect", response_model=ArchitectResponse)
async def create_plan(request: ArchitectRequest):
    # Placeholder for actual LangChain agent logic
    # Here you would generate an academic plan based on goals and skills
    
    plan_result = f"Mocked academic plan to transition from '{request.current_skills}' to '{request.career_goal}'. Suggested courses: CS101, Data Structures."
    
    return ArchitectResponse(
        status="success",
        academic_plan=plan_result
    )

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "academic_architect"}
