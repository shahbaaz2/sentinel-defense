"""Every action a scenario step can perform - and nothing else. Each function makes exactly one
real HTTP call to MissionNet's public or lab-control API. There is no action here, or anywhere in
this package, that writes to Sentinel or fabricates a MissionNet event - that is the whole point
of the Scenario Controller's safety boundary (blueprint §17, Phase 3 continuation prompt §3).

Every call also forwards `scenario_id` (injected into `parameters` by the runner before dispatch)
so MissionNet's own audit trail - and, downstream, Sentinel's NormalizedEventRecord.scenario_id -
carries genuine scenario provenance end to end, not just within Demo Control's own run record.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from apps.demo_control.config import settings
from services.sensor_lab.pipeline import SensorLabError, run_network_sensor_lab

# A cloud host's own edge/gateway returns these on a cold start or a brief restart - genuinely
# transient, safe to retry. Everything else (4xx application errors, 500s from the app itself) is
# a real failure and must never be retried into a fake success.
_TRANSIENT_STATUS_CODES = {502, 503, 504}
_MAX_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 0.5
_ERROR_DETAIL_LIMIT = 300


class ActionError(Exception):
    def __init__(self, action: str, detail: str):
        super().__init__(f"action {action!r} failed: {detail}")
        self.action = action
        self.detail = detail


def _lab_headers() -> dict[str, str]:
    return {"X-Lab-Secret": settings.missionnet_lab_secret}


def _short_detail(resp: httpx.Response) -> str:
    """Never let a proxy's HTML error page (a Render/nginx-style 502 page can be several KB) end
    up verbatim in an ActionError message - it becomes a ScenarioRun.failure_reason, which the
    Demo Control console and the live-demo GUI both may show directly to a viewer."""
    text = resp.text.strip().replace("\n", " ")
    if len(text) > _ERROR_DETAIL_LIMIT:
        text = text[:_ERROR_DETAIL_LIMIT] + "…"
    return text


async def _post(client: httpx.AsyncClient, path: str, **kwargs) -> dict:
    resp = await client.post(path, **kwargs)
    if resp.status_code >= 400:
        raise ActionError(path, f"{resp.status_code}: {_short_detail(resp)}")
    return resp.json()


async def _get(client: httpx.AsyncClient, path: str, **kwargs) -> dict:
    resp = await client.get(path, **kwargs)
    if resp.status_code >= 400:
        raise ActionError(path, f"{resp.status_code}: {_short_detail(resp)}")
    return resp.json()


async def _get_with_bounded_retry(client: httpx.AsyncClient, path: str, **kwargs) -> dict:
    """Retries only a transient gateway status (502/503/504) or a transport-level failure
    (connection reset, timeout) - up to `_MAX_ATTEMPTS` total tries with a short linear backoff.
    A genuine application error (4xx, or a 500 from the app itself) raises immediately on the
    first attempt and is never retried into a fake success - see DECISIONS.md."""
    last_exc: Exception | None = None
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            resp = await client.get(path, **kwargs)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            last_exc = ActionError(path, f"transport error on attempt {attempt}: {exc}")
        else:
            if resp.status_code not in _TRANSIENT_STATUS_CODES:
                if resp.status_code >= 400:
                    raise ActionError(path, f"{resp.status_code}: {_short_detail(resp)}")
                return resp.json()
            last_exc = ActionError(
                path, f"{resp.status_code} (transient gateway error) on attempt {attempt}"
            )

        if attempt < _MAX_ATTEMPTS:
            await asyncio.sleep(_RETRY_BACKOFF_SECONDS * attempt)

    assert last_exc is not None  # the loop always sets it before falling through
    raise last_exc


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
    """The one action with bounded retry: a public cloud deployment's edge can return a
    transient 502/503/504 on a cold start. `run_id`/`step_id` (injected by the runner, see
    apps/demo_control/runner.py) let MissionNet's own endpoint treat a retried call as the exact
    same logical action - it reuses the same audit_id instead of creating a second
    record.access AuditEvent - so retrying here is safe even though the endpoint has a genuine
    side effect (see docs/demo-runbook.md and DECISIONS.md)."""
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
