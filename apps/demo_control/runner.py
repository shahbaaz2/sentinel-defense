"""Scenario execution state machine.

PENDING -> PREPARING -> RUNNING -> WAITING_FOR_TELEMETRY -> WAITING_FOR_SENTINEL -> VERIFYING ->
PASSED | FAILED, with CANCELLED reachable at any point before a terminal state.

This module is the one place that ties actions.py (MissionNet calls), verification.py (Sentinel
read-only checks), and persistence together - and it is intentionally the *only* place. It never
calls anything that writes to Sentinel's events/detections/incidents tables; the only Sentinel
calls it makes are GET requests and the one legitimate POST /api/v1/ingest/run, which runs
Sentinel's real, unmodified ingestion pipeline (see DECISIONS.md).
"""

import asyncio
import logging
from datetime import datetime

import httpx

from apps.demo_control.actions import ACTIONS, ActionError
from apps.demo_control.config import settings
from apps.demo_control.db import SessionLocal
from apps.demo_control.models import ScenarioRun
from apps.demo_control.scenarios import ScenarioDefinition, ScenarioStep, load_scenario
from apps.demo_control.verification import (
    Baseline,
    VerificationResult,
    capture_baseline,
    verify_scenario_result,
)

logger = logging.getLogger("demo_control.runner")

TERMINAL_STATES = {"PASSED", "FAILED", "CANCELLED"}


async def _load_run(run_id: str) -> ScenarioRun | None:
    async with SessionLocal() as session:
        return await session.get(ScenarioRun, run_id)


async def _update_run(run_id: str, **fields) -> ScenarioRun:
    async with SessionLocal() as session:
        run = await session.get(ScenarioRun, run_id)
        if run is None:
            raise ValueError(f"scenario run {run_id} not found")
        for key, value in fields.items():
            setattr(run, key, value)
        await session.commit()
        await session.refresh(run)
        return run


async def _append_timeline(run_id: str, message: str) -> None:
    async with SessionLocal() as session:
        run = await session.get(ScenarioRun, run_id)
        if run is None:
            return
        entry = {"timestamp": datetime.now().astimezone().isoformat(), "message": message}
        run.timeline = [*run.timeline, entry]
        await session.commit()


async def _is_cancelled(run_id: str) -> bool:
    run = await _load_run(run_id)
    return run is not None and run.cancel_requested


async def _reset_lab() -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        mn_resp = await client.post(
            f"{settings.missionnet_base_url}/lab/reset",
            headers={"X-Lab-Secret": settings.missionnet_lab_secret},
        )
        mn_resp.raise_for_status()
        sentinel_resp = await client.post(f"{settings.sentinel_base_url}/api/v1/admin/reset")
        sentinel_resp.raise_for_status()
    return {"missionnet": mn_resp.json(), "sentinel": sentinel_resp.json()}


def _expand_steps(steps: list[ScenarioStep]) -> list[tuple[ScenarioStep, str]]:
    """Expands `repeat` and `targets` into a flat (step, target) execution list."""
    expanded = []
    for step in steps:
        if step.targets:
            for target in step.targets:
                expanded.append((step, target))
        elif step.target:
            for _ in range(step.repeat):
                expanded.append((step, step.target))
        else:
            expanded.append((step, ""))
    return expanded


async def run_scenario(run_id: str) -> None:
    run = await _load_run(run_id)
    if run is None:
        logger.error("run %s vanished before execution started", run_id)
        return

    try:
        scenario = load_scenario(run.scenario_id)
    except Exception as exc:  # noqa: BLE001 - any parse error is a genuine run failure
        await _update_run(
            run_id,
            status="FAILED",
            failure_reason=f"could not load scenario definition: {exc}",
            completed_at=datetime.now().astimezone(),
        )
        return

    try:
        await _execute(run_id, scenario)
    except Exception as exc:  # noqa: BLE001 - convert any unexpected error into a visible FAILED
        logger.exception("scenario run %s failed with an unhandled error", run_id)
        await _append_timeline(run_id, f"Scenario failed: {exc}")
        await _update_run(
            run_id,
            status="FAILED",
            failure_reason=str(exc),
            completed_at=datetime.now().astimezone(),
        )


async def _execute(run_id: str, scenario: ScenarioDefinition) -> None:
    await _update_run(run_id, status="PREPARING", current_step="preconditions")
    await _append_timeline(run_id, "Scenario preparing")

    async with httpx.AsyncClient(base_url=settings.missionnet_base_url, timeout=15.0) as mn_client:
        health = (await mn_client.get("/health")).json()
        missionnet_ok = health.get("status") is not None

    if not missionnet_ok:
        await _fail(run_id, "MissionNet unavailable")
        return

    try:
        async with httpx.AsyncClient(base_url=settings.sentinel_base_url, timeout=15.0) as s_client:
            await s_client.get("/api/v1/health")
    except httpx.HTTPError:
        await _fail(run_id, "Sentinel unavailable")
        return

    if scenario.reset.strategy == "lab_reset":
        await _append_timeline(run_id, "Resetting lab to deterministic baseline")
        try:
            await _reset_lab()
        except httpx.HTTPError as exc:
            await _fail(run_id, f"lab reset failed: {exc}")
            return
        await _append_timeline(run_id, "MissionNet baseline verified")

    async with httpx.AsyncClient(base_url=settings.missionnet_base_url, timeout=15.0) as mn_client:
        state = (await mn_client.get("/state")).json()
    if state["status"] != scenario.preconditions.missionnet_status:
        await _fail(
            run_id,
            f"precondition failed: expected MissionNet status "
            f"{scenario.preconditions.missionnet_status!r}, got {state['status']!r}",
        )
        return

    run_started_at = datetime.now().astimezone()
    async with httpx.AsyncClient(base_url=settings.sentinel_base_url, timeout=15.0) as s_client:
        baseline = await capture_baseline(s_client)

    await _update_run(run_id, status="RUNNING", current_step="steps")
    step_results = []
    missionnet_responses = []

    async with httpx.AsyncClient(base_url=settings.missionnet_base_url, timeout=15.0) as mn_client:
        for step, target in _expand_steps(scenario.steps):
            if await _is_cancelled(run_id):
                await _finish_cancelled(run_id)
                return

            action_fn = ACTIONS.get(step.action)
            if action_fn is None:
                await _fail(run_id, f"unknown scenario action: {step.action!r}")
                return

            await _update_run(run_id, current_step=step.id)
            try:
                response = await action_fn(mn_client, target, step.parameters)
                step_results.append(
                    {
                        "step_id": step.id,
                        "action": step.action,
                        "target": target,
                        "response": response,
                    }
                )
                missionnet_responses.append(response)
                await _append_timeline(run_id, f"{step.action} -> {target}")
            except ActionError as exc:
                await _fail(run_id, f"step {step.id} ({step.action}) failed: {exc}")
                return

    await _update_run(run_id, step_results=step_results, status="WAITING_FOR_TELEMETRY")
    await _append_timeline(run_id, "MissionNet actions complete - waiting for audit/telemetry")

    missionnet_event_ids = await _poll_missionnet_events(
        run_id, scenario, run_started_at
    )
    if missionnet_event_ids is None:
        await _fail(run_id, "expected MissionNet event(s) not observed within timeout")
        return
    await _update_run(run_id, missionnet_event_ids=missionnet_event_ids)
    await _append_timeline(
        run_id, f"MissionNet event(s) observed ({len(missionnet_event_ids)})"
    )

    await _update_run(run_id, status="WAITING_FOR_SENTINEL")
    await _append_timeline(run_id, "Triggering Sentinel ingestion")

    verification = await _poll_sentinel_pipeline(run_id, scenario, baseline, run_started_at)
    if verification is None:
        await _fail(run_id, "Sentinel did not produce the expected detection/incident in time")
        return

    verification.checks["missionnet_event_observed"] = True
    await _append_timeline(run_id, "Sentinel normalized event(s) observed")
    if verification.detection_ids:
        await _append_timeline(run_id, f"Detection(s) triggered: {len(verification.detection_ids)}")
    if verification.incident_ids:
        await _append_timeline(
            run_id, f"Incident(s) created: {', '.join(verification.incident_ids)}"
        )
    await _append_timeline(run_id, "Evidence links verified")

    await _update_run(run_id, status="VERIFYING")

    passed = verification.all_passed
    await _update_run(
        run_id,
        status="PASSED" if passed else "FAILED",
        sentinel_event_ids=verification.sentinel_event_ids,
        detection_ids=verification.detection_ids,
        incident_ids=verification.incident_ids,
        verification=verification.checks,
        failure_reason=None if passed else f"verification failed: {verification.checks}",
        completed_at=datetime.now().astimezone(),
        current_step=None,
    )
    await _append_timeline(run_id, "Scenario PASSED" if passed else "Scenario FAILED")


async def _poll_missionnet_events(
    run_id: str, scenario: ScenarioDefinition, since: datetime
) -> list[str] | None:
    deadline = asyncio.get_event_loop().time() + settings.poll_timeout_seconds
    expected = scenario.expected_observations.missionnet

    async with httpx.AsyncClient(base_url=settings.missionnet_base_url, timeout=15.0) as mn_client:
        while True:
            if await _is_cancelled(run_id):
                return None
            audit = (
                await mn_client.get("/audit", params={"since": since.isoformat(), "limit": 500})
            ).json()
            telemetry = (
                await mn_client.get(
                    "/telemetry", params={"since": since.isoformat(), "limit": 500}
                )
            ).json()

            all_ok = True
            for exp in expected:
                if exp.event_type == "telemetry.sample":
                    matches = [
                        t for t in telemetry if not exp.asset_id or t["asset_id"] == exp.asset_id
                    ]
                else:
                    matches = [
                        a
                        for a in audit
                        if a["action"] == exp.event_type
                        and (not exp.asset_id or a["object_id"] == exp.asset_id)
                    ]
                if len(matches) < exp.count:
                    all_ok = False

            if all_ok:
                ids = [f"missionnet-audit-{a['audit_id']}" for a in audit]
                ids += [f"missionnet-telemetry-{t['sample_id']}" for t in telemetry]
                return ids

            if asyncio.get_event_loop().time() >= deadline:
                return None
            await asyncio.sleep(settings.poll_interval_seconds)


async def _poll_sentinel_pipeline(
    run_id: str,
    scenario: ScenarioDefinition,
    baseline: Baseline,
    run_started_at: datetime,
) -> VerificationResult | None:
    deadline = asyncio.get_event_loop().time() + settings.poll_timeout_seconds
    last_result: VerificationResult | None = None

    async with httpx.AsyncClient(base_url=settings.sentinel_base_url, timeout=30.0) as s_client:
        while True:
            if await _is_cancelled(run_id):
                return None
            await s_client.post("/api/v1/ingest/run")
            last_result = await verify_scenario_result(s_client, scenario, baseline, run_started_at)

            core_ready = (
                last_result.checks.get("expected_detection_observed")
                and last_result.checks.get("incident_created")
            )
            if core_ready:
                return last_result

            if asyncio.get_event_loop().time() >= deadline:
                return last_result
            await asyncio.sleep(settings.poll_interval_seconds)


async def _fail(run_id: str, reason: str) -> None:
    await _append_timeline(run_id, f"Scenario failed: {reason}")
    await _update_run(
        run_id, status="FAILED", failure_reason=reason, completed_at=datetime.now().astimezone()
    )


async def _finish_cancelled(run_id: str) -> None:
    await _append_timeline(run_id, "Scenario cancelled")
    await _update_run(run_id, status="CANCELLED", completed_at=datetime.now().astimezone())


async def reset_after_run(run_id: str) -> None:
    run = await _load_run(run_id)
    if run is None:
        raise ValueError(f"scenario run {run_id} not found")
    try:
        await _reset_lab()
        await _update_run(run_id, reset_status="RESET_COMPLETE")
    except httpx.HTTPError as exc:
        await _update_run(run_id, reset_status=f"RESET_FAILED: {exc}")
        raise
