from fastapi import FastAPI

from apps.api.admin_routes import router as admin_router
from apps.api.config import settings
from apps.api.routes import router as api_router

app = FastAPI(title="Sentinel API", version="0.3.0")
app.include_router(api_router)
app.include_router(admin_router)


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok", "service": "sentinel-api", "env": settings.env}


@app.get("/api/v1/system/profile")
async def system_profile() -> dict:
    return {"profile": settings.profile, "synthetic_only": settings.synthetic_only}


@app.get("/api/v1/system/assurance")
async def system_assurance() -> dict:
    """Makes the local/offline claim observable rather than merely asserted (blueprint §16.8)."""
    return {
        "inference_location": "local",
        "external_ai_api": "disabled" if not settings.external_ai_enabled else "enabled",
        "model": settings.llm_model,
        "model_provider": settings.llm_provider,
        "knowledge_bundle": settings.knowledge_bundle,
        "policy_bundle": settings.policy_bundle,
        "synthetic_only": settings.synthetic_only,
    }
