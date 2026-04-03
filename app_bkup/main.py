from fastapi import FastAPI

from app.config import settings
from app.apiroutes.campaigns_routes import router as campaigns_routes_router
from app.apiroutes.content_ideas import router as content_ideas_router
from app.apiroutes.generation import router as generation_router
from app.apiroutes.debug import router as debug_router
from app.apiroutes.approvals import router as approvals_router
from app.apiroutes.assets import router as assets_router
from app.apiroutes.publishing import router as publishing_router
from app.apiroutes.insights import router as insights_router
from app.apiroutes.pipeline import router as pipeline_router
from app.apiroutes.cinematic_pipeline import router as cinematic_pipeline_router
from app.apiroutes.pipeline_selector import router as pipeline_selector_router


app = FastAPI(
    title="AI Content Agent",
    version="1.0.0"
)



@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}



app.include_router(campaigns_routes_router)
app.include_router(content_ideas_router)
app.include_router(generation_router)
app.include_router(debug_router)
app.include_router(approvals_router)
app.include_router(assets_router)
app.include_router(publishing_router)
app.include_router(insights_router)
app.include_router(pipeline_router)
app.include_router(cinematic_pipeline_router)
app.include_router(pipeline_selector_router)
