from fastapi import FastAPI

from backend.market_scout.api.routes import router

app = FastAPI(title="Market Scout Agent")
app.include_router(router)
