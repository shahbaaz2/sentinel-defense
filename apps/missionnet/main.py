"""MissionNet shell (Phase 0).

The real synthetic application - Identity, Mission Data, Telemetry Gateway, Asset Registry, seeded
dataset, lab-control API - is built in Phase 1. This shell exists only to prove MissionNet is
independently runnable, separate from Sentinel, from day one.
"""

from fastapi import FastAPI

app = FastAPI(title="MissionNet", version="0.1.0")


@app.get("/health")
async def health() -> dict:
    return {
        "status": "nominal",
        "classification": "SYNTHETIC",
        "service": "missionnet",
        "note": "Phase 0 shell - full Operations Console lands in Phase 1.",
    }
