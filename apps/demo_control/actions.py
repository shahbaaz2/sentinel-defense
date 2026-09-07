"""Every action a scenario step can perform - and nothing else. Each function makes exactly one
real HTTP call to MissionNet's public or lab-control API. There is no action here, or anywhere in
this package, that writes to Sentinel or fabricates a MissionNet event - that is the whole point
of the Scenario Controller's safety boundary (blueprint §17, Phase 3 continuation prompt §3).

Every call also forwards `scenario_id` (injected into `parameters` by the runner before dispatch)
so MissionNet's own audit trail - and, downstream, Sentinel's NormalizedEventRecord.scenario_id -
carries genuine scenario provenance end to end, not just within Demo Control's own run record.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from apps.demo_control.config import settings
from services.sensor_lab.pipeline import SensorLabError, run_network_sensor_lab


class ActionError(Exception):
    def __init__(self, action: str, detail: str):
        super().__init__(f"action {action!r} failed: {detail}")
        self.action = action
        self.detail = detail


def _lab_headers() -> dict[str, str]:
    return {"X-Lab-Secret": settings.missionnet_lab_secret}


async def _post(client: httpx.AsyncClient, path: str, **kwargs) -> dict:
    resp = await client.post(path, **kwargs)
    if resp.status_code >= 400:
        raise ActionError(path, f"{resp.status_code}: {resp.text}")
    return resp.json()


async def _get(client: httpx.AsyncClient, path: str, **kwargs) -> dict:
    resp = await client.get(path, **kwargs)
    if resp.status_code >= 400:
        raise ActionError(path, f"{resp.status_code}: {resp.text}")
    return resp.json()


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
    actor_user_id = parameters["actor_user_id"]
    params = {"actor_user_id": actor_user_id}
    if parameters.get("scenario_id"):
        params["scenario_id"] = parameters["scenario_id"]
    return await _get(client, f"/mission-data/records/{target}", params=params)


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
    """The one non-MissionNet action: generates safe synthetic lab traffic between ephemeral
    Docker containers and runs real Suricata/Zeek against it (services/sensor_lab/pipeline.py).
    `client`/`target` are unused - this step needs neither MissionNet nor a per-step target - kept
    only so this function still satisfies `ActionFn`'s shared signature."""
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
