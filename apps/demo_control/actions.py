"""Every action a scenario step can perform - and nothing else.

Each function makes exactly one logical call to MissionNet's public or lab-control API. There is no
action here, or anywhere in this package, that writes to Sentinel or fabricates a MissionNet event.
Every call forwards scenario provenance so later verification can prove the evidence chain.

Cloud reliability is handled by ``apps.demo_control.http_client``. Side-effecting actions are never
blindly retried unless the operation is explicitly known to be replay-safe. A successful 2xx with
an empty/non-JSON body is accepted as transport metadata because the later evidence-verification
stage - not the response body - decides whether the action actually occurred.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from apps.demo_control.config import settings
from apps.demo_control.http_client import (
    ERROR_DETAIL_LIMIT,
    MAX_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    TRANSIENT_STATUS_CODES,
    UpstreamResponseError,
    request_json,
    short_detail,
)
from services.sensor_lab.pipeline import SensorLabError, run_network_sensor_lab

# Backward-compatible module constants used by existing tests/documentation.
_TRANSIENT_STATUS_CODES = TRANSIENT_STATUS_CODES
_MAX_ATTEMPTS = MAX_ATTEMPTS
_RETRY_BACKOFF_SECONDS = RETRY_BACKOFF_SECONDS
_ERROR_DETAIL_LIMIT = ERROR_DETAIL_LIMIT


class ActionError(Exception):
    def __init__(self, action: str, detail: str):
        super().__init__(f"action {action!r} failed: {detail}")
        self.action = action
        self.detail = detail


def _lab_headers() -> dict[str, str]:
    return {"X-Lab-Secret": settings.missionnet_lab_secret}


def _short_detail(resp: httpx.Response) -> str:
    """Compatibility wrapper around the centralized bounded response formatter."""
    return short_detail(resp)


async def _action_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    retry_safe: bool = False,
    **kwargs: Any,
) -> dict:
    try:
        result = await request_json(
            client,
            method,
            path,
            component="MissionNet",
            retry_safe=retry_safe,
            allow_non_json_success=True,
            **kwargs,
        )
    except UpstreamResponseError as exc:
        raise ActionError(path, str(exc)) from exc
    if not isinstance(result, dict):
        # MissionNet action APIs are expected to return objects. A non-object 2xx response is not
        # used as evidence, so preserve only transport metadata and let verification decide truth.
        return {"accepted": True, "http_status": 200, "response_format": type(result).__name__}
    return result


async def _post(client: httpx.AsyncClient, path: str, **kwargs) -> dict:
    return await _action_request(client, "POST", path, retry_safe=False, **kwargs)


async def _get(client: httpx.AsyncClient, path: str, **kwargs) -> dict:
    return await _action_request(client, "GET", path, retry_safe=False, **kwargs)


async def _get_with_bounded_retry(client: httpx.AsyncClient, path: str, **kwargs) -> dict:
    """Retry a replay-safe GET only for bounded cloud-edge/transport failure modes."""
    return await _action_request(client, "GET", path, retry_safe=True, **kwargs)


async def auth_failure(client: httpx.AsyncClient, target: str, parameters: dict) -> dict:
    return await _post(
        client,
        "/identity/login",
        json={
            "username": target,
            "password": "wrong-on-purpose",
            "scenario_id": parameters.get("scenario_id"),
        },
    )


async def auth_success(client: httpx.AsyncClient, target: str, parameters: dict) -> dict:
    password = parameters.get("password", "SynthLab#2026")
    return await _post(
        client,
        "/identity/login",
        json={
            "username": target,
            "password": password,
            "scenario_id": parameters.get("scenario_id"),
        },
    )


async def degrade_asset(client: httpx.AsyncClient, target: str, parameters: dict) -> dict:
    return await _post(
        client,
        f"/lab/state/{target}/degrade",
        headers=_lab_headers(),
        json={
            "reason": parameters.get("reason", "synthetic_lab_scenario"),
            "scenario_id": parameters.get("scenario_id"),
        },
    )


async def quarantine_asset(client: httpx.AsyncClient, target: str, parameters: dict) -> dict:
    return await _post(
        client,
        f"/lab/assets/{target}/quarantine",
        headers=_lab_headers(),
        json={
            "reason": parameters.get("reason", "synthetic_lab_scenario"),
            "scenario_id": parameters.get("scenario_id"),
        },
    )


async def restore_asset(client: httpx.AsyncClient, target: str, parameters: dict) -> dict:
    return await _post(
        client,
        f"/lab/assets/{target}/restore",
        headers=_lab_headers(),
        json={
            "reason": parameters.get("reason", "synthetic_lab_scenario"),
            "scenario_id": parameters.get("scenario_id"),
        },
    )


async def revoke_token(client: httpx.AsyncClient, target: str, parameters: dict) -> dict:
    return await _post(
        client,
        f"/lab/tokens/{target}/revoke",
        headers=_lab_headers(),
        json={
            "reason": parameters.get("reason", "synthetic_lab_scenario"),
            "scenario_id": parameters.get("scenario_id"),
        },
    )


async def inject_telemetry(client: httpx.AsyncClient, target: str, parameters: dict) -> dict:
    return await _post(
        client,
        f"/lab/telemetry/{target}/inject",
        headers=_lab_headers(),
        json={
            "battery": parameters.get("battery", 90),
            "link_quality": parameters.get("link_quality", 95),
            "scenario_id": parameters.get("scenario_id"),
        },
    )


async def access_record(client: httpx.AsyncClient, target: str, parameters: dict) -> dict:
    """Record access is replay-safe because run_id/step_id make MissionNet audit creation idempotent."""
    actor_user_id = parameters["actor_user_id"]
    params = {"actor_user_id": actor_user_id}
    if parameters.get("scenario_id"):
        params["scenario_id"] = parameters["scenario_id"]
    if parameters.get("run_id"):
        params["run_id"] = parameters["run_id"]
    if parameters.get("step_id"):
        params["step_id"] = parameters["step_id"]
    return await _get_with_bounded_retry(client, f"/mission-data/records/{target}", params=params)


async def snapshot_evidence(client: httpx.AsyncClient, target: str, parameters: dict) -> dict:
    return await _post(
        client,
        "/lab/evidence/snapshot",
        headers=_lab_headers(),
        json={"scenario_id": parameters.get("scenario_id")},
    )


async def run_network_sensor_lab_action(
    client: httpx.AsyncClient, target: str, parameters: dict
) -> dict:
    try:
        result = await run_network_sensor_lab()
    except SensorLabError as exc:
        raise ActionError("run_network_sensor_lab", str(exc)) from exc
    return {
        "pcap_path": result.pcap_path,
        "suricata_alert_count": result.suricata_alert_count,
        "zeek_conn_count": result.zeek_conn_count,
        "zeek_dns_count": result.zeek_dns_count,
        "zeek_http_count": result.zeek_http_count,
    }


ActionFn = Callable[[httpx.AsyncClient, str, dict[str, Any]], Awaitable[dict]]

ACTIONS: dict[str, ActionFn] = {
    "auth_failure": auth_failure,
    "auth_success": auth_success,
    "degrade_asset": degrade_asset,
    "quarantine_asset": quarantine_asset,
    "restore_asset": restore_asset,
    "revoke_token": revoke_token,
    "inject_telemetry": inject_telemetry,
    "access_record": access_record,
    "snapshot_evidence": snapshot_evidence,
    "run_network_sensor_lab": run_network_sensor_lab_action,
}
