"""Demo Control: the Scenario/Demo Control Plane (blueprint §17, Phase 3).

Its only job is orchestration - start a named scenario, drive MissionNet through approved
public/lab APIs, and observe whatever Sentinel independently produces. It never writes to
Sentinel's event/detection/incident tables and never marks a check passed without a real API
response backing it. See DECISIONS.md for the full safety-boundary rationale.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.demo_control.routes import router as demo_control_router

app = FastAPI(title="Sentinel Demo Control", version="0.1.0")
app.include_router(demo_control_router)

# The Demo Control Console (Next.js, :3200) calls this API directly from browser JS - a different
# origin, so it needs CORS enabled. Restricted to localhost dev ports; this API is never intended
# to be reachable outside the local lab.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3200", "http://localhost:3200"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "demo-control"}
