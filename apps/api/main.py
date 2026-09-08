from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.admin_routes import router as admin_router
from apps.api.ai_routes import router as ai_router
from apps.api.assurance_routes import router as assurance_router
from apps.api.audit_routes import router as audit_router
from apps.api.config import settings
from apps.api.coverage_routes import router as coverage_router
from apps.api.execution_routes import router as execution_router
from apps.api.integration_routes import router as integration_router
from apps.api.response_routes import router as response_router
from apps.api.routes import router as api_router
from apps.api.stream_routes import router as stream_router

app = FastAPI(title="Sentinel API", version="0.8.0")
app.include_router(api_router)
app.include_router(admin_router)
app.include_router(ai_router)
app.include_router(assurance_router)
app.include_router(audit_router)
app.include_router(coverage_router)
app.include_router(execution_router)
app.include_router(integration_router)
app.include_router(response_router)
app.include_router(stream_router)

# The dashboard opens a Server-Sent-Events connection to /api/v1/stream from browser JS - a
# different origin, so it needs CORS enabled. Origins come from settings (SENTINEL_CORS_ALLOWED_
# ORIGINS) so a cloud deployment can lock this to its real Vercel domain(s) instead of the local
# default - see docs/deployment.md.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok", "service": "sentinel-api", "env": settings.env}


@app.get("/api/v1/system/profile")
async def system_profile() -> dict:
    return {"profile": settings.profile, "synthetic_only": settings.synthetic_only}
