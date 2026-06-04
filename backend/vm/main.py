from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from course_search_tool import CourseSearchTool

app = FastAPI(title="VM Task Server")
searcher = CourseSearchTool()

class SearchRequest(BaseModel):
    query: str

@app.post("/search")
async def search_courses(request: SearchRequest):
    try:
        results = await searcher.search_all(request.query)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "vm_server"}
