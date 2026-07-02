from fastapi import FastAPI

from api.routes import router as system_router
from assessments.routes import router as assessments_router
from cv_intake.routes import router as cv_router
from holland.routes import router as holland_router
from profile_scan.routes import router as profile_router


app = FastAPI(title="Profile Scanner Agent")

app.include_router(system_router)
app.include_router(profile_router)
app.include_router(assessments_router)
app.include_router(holland_router)
app.include_router(cv_router)
