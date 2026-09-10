"""Dependency warm-up endpoint for the employer-facing scenario console.

This endpoint exists so the UI can wake cloud services before an operator is allowed to start a
scenario run. It does not execute a scenario, mutate MissionNet, or create Sentinel evidence. It
only performs read-only readiness probes and reports whether the controlled lab is ready.
"""

import asyncio

import httpx
from fastapi import APIRouter

from apps.demo_control.config import settings
from apps.demo_control.http_client import UpstreamResponseError, request_json

router = APIRouter(prefix="/api/v1")


async def _probe_missionnet(client: httpx.AsyncClient) -> dict:
    try:
        state = await request_json(
            client,
            "GET",
            f"{settings.missionnet_base_url}/state",
            component="MissionNet",
            retry_safe=False,
            expected_type=dict,
        )
        return {
            "ready": True,
            "status": str(state.get("status", "READY")).upper(),
            "detail": "MissionNet application and datastore are reachable.",
        }
    except UpstreamResponseError as exc:
        return {
            "ready": False,
            "status": "WARMING" if exc.code in {
                "UPSTREAM_GATEWAY_ERROR",
                "UPSTREAM_TRANSPORT_ERROR",
                "UPSTREAM_INVALID_RESPONSE",
            } else "UNAVAILABLE",
            "detail": "MissionNet is waking on the cloud runtime. No scenario has started yet.",
            "code": exc.code,
        }


async def _probe_sentinel(client: httpx.AsyncClient) -> dict:
    try:
        await request_json(
            client,
            "GET",
            f"{settings.sentinel_base_url}/api/v1/health",
            component="Sentinel API",
            retry_safe=False,
            allow_non_json_success=True,
        )
        return {
            "ready": True,
            "status": "ONLINE",
            "detail": "Sentinel API is reachable.",
        }
    except UpstreamResponseError as exc:
        return {
            "ready": False,
            "status": "WARMING" if exc.code in {
                "UPSTREAM_GATEWAY_ERROR",
                "UPSTREAM_TRANSPORT_ERROR",
                "UPSTREAM_INVALID_RESPONSE",
            } else "UNAVAILABLE",
            "detail": "Sentinel API is waking on the cloud runtime.",
            "code": exc.code,
        }


@router.get("/warmup")
async def warmup_dependencies() -> dict:
    """Wake and verify both lab dependencies without creating a scenario run."""
    async with httpx.AsyncClient(timeout=6.0) as client:
        missionnet, sentinel = await asyncio.gather(
            _probe_missionnet(client),
            _probe_sentinel(client),
        )

    ready = bool(missionnet["ready"] and sentinel["ready"])
    return {
        "ready": ready,
        "phase": "READY" if ready else "WARMING",
        "message": (
            "Controlled lab is ready for scenario execution."
            if ready
            else "Cloud lab services are being prepared before scenario execution."
        ),
        "missionnet": missionnet,
        "sentinel": sentinel,
    }
