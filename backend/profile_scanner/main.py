import time
import uuid

from fastapi import FastAPI
from fastapi import Request

from api.routes import router as system_router
from assessments.routes import router as assessments_router
from canonical_profile.routes import router as canonical_profile_router
from capabilities.routes import router as capabilities_router
from career_alignment.routes import router as career_alignment_router
from cv_intake.routes import router as cv_router
from holland.routes import router as holland_router
from profile_scan.routes import router as profile_router


app = FastAPI(title="Profile Scanner Agent")


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        from core.config import logger

        logger.exception(
            "Profile Scanner request failed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
            },
        )
        raise
    response.headers["X-Request-ID"] = request_id
    from core.config import logger

    logger.info(
        "Profile Scanner request completed",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
        },
    )
    return response

app.include_router(system_router)
app.include_router(profile_router)
app.include_router(assessments_router)
app.include_router(canonical_profile_router)
app.include_router(career_alignment_router)
app.include_router(capabilities_router)
app.include_router(holland_router)
app.include_router(cv_router)
