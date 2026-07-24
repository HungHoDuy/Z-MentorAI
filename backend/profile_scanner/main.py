from fastapi import FastAPI

from api.routes import router as system_router
from assessments.routes import router as assessments_router
from canonical_profile.routes import router as canonical_profile_router
from capabilities.routes import router as capabilities_router
from career_alignment.routes import router as career_alignment_router
from cv_intake.routes import router as cv_router
from holland.routes import router as holland_router
from profile_scan.routes import router as profile_router


app = FastAPI(title="Profile Scanner Agent")

app.include_router(system_router)
app.include_router(profile_router)
app.include_router(assessments_router)
app.include_router(canonical_profile_router)
app.include_router(career_alignment_router)
app.include_router(capabilities_router)
app.include_router(holland_router)
app.include_router(cv_router)
