from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.admin_routes import router as admin_router
from apps.api.assurance_routes import router as assurance_router
from apps.api.audit_routes import router as audit_router
from apps.api.config import settings
from apps.api.coverage_routes import router as coverage_router
from apps.api.routes import router as api_router
from apps.api.stream_routes import router as stream_router

app = FastAPI(title="Sentinel API", version="0.4.0")
app.include_router(api_router)
app.include_router(admin_router)
app.include_router(assurance_router)
app.include_router(audit_router)
app.include_router(coverage_router)
app.include_router(stream_router)

# The dashboard (:3000) opens a Server-Sent-Events connection to /api/v1/stream from browser JS - a
# different origin, so it needs CORS enabled, same reasoning as Demo Control's console (:3200).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok", "service": "sentinel-api", "env": settings.env}


@app.get("/api/v1/system/profile")
async def system_profile() -> dict:
    return {"profile": settings.profile, "synthetic_only": settings.synthetic_only}
