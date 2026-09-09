"""Scenario execution state machine.

PENDING -> PREPARING -> RUNNING -> WAITING_FOR_TELEMETRY -> WAITING_FOR_SENTINEL -> VERIFYING ->
PASSED | FAILED, with CANCELLED reachable before a terminal state.

The runner orchestrates approved MissionNet actions and observes Sentinel's real pipeline. It never
fabricates detections/incidents. Cloud-edge and integration failures are classified before they are
persisted so the operator gets an actionable component/operation error instead of a raw decoder or
proxy exception.
"""

import asyncio
import logging
from datetime import datetime

import httpx

from apps.demo_control.actions import ACTIONS, ActionError
from apps.demo_control.config import settings
from apps.demo_control.db import SessionLocal
from apps.demo_control.http_client import UpstreamResponseError, request_json
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


def _reason_code(reason: str) -> str | None:
    start = reason.find("[")
    end = reason.find("]", start + 1)
    if start >= 0 and end > start:
        candidate = reason[start + 1 : end]
        if candidate and all(ch.isupper() or ch.isdigit() or ch == "_" for ch in candidate):
            return candidate
    return None


async def _append_timeline(
    run_id: str,
    message: str,
    *,
    level: str = "INFO",
    code: str | None = None,
    component: str = "Demo Control",
) -> None:
    """Persist an operator-readable run log entry without requiring a schema migration."""
    async with SessionLocal() as session:
        run = await session.get(ScenarioRun, run_id)
        if run is None:
            return
        entry = {
            "timestamp": datetime.now().astimezone().isoformat(),
            "message": message,
            "level": level,
            "component": component,
        }
        if code:
            entry["code"] = code
        run.timeline = [*run.timeline, entry]
        await session.commit()


async def _is_cancelled(run_id: str) -> bool:
    run = await _load_run(run_id)
    return run is not None and run.cancel_requested


async def _reset_lab() -> dict:
    """Reset both lab systems. Both reset operations are deterministic/idempotent and retry-safe."""
    async with httpx.AsyncClient(timeout=15.0) as client:
        missionnet = await request_json(
            client,
            "POST",
            f"{settings.missionnet_base_url}/lab/reset",
            component="MissionNet",
            retry_safe=True,
            allow_non_json_success=True,
            headers={"X-Lab-Secret": settings.missionnet_lab_secret},
        )
        sentinel = await request_json(
            client,
            "POST",
            f"{settings.sentinel_base_url}/api/v1/admin/reset",
            component="Sentinel API",
            retry_safe=True,
            allow_non_json_success=True,
        )
    return {"missionnet": missionnet, "sentinel": sentinel}


def _expand_steps(steps: list[ScenarioStep]) -> list[tuple[ScenarioStep, str]]:
    """Expand ``repeat`` and ``targets`` into a flat logical execution list."""
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
        logger.error("scenario_run_missing run_id=%s", run_id)
        return

    logger.info("scenario_run_started run_id=%s scenario_id=%s", run_id, run.scenario_id)

    try:
        scenario = load_scenario(run.scenario_id)
    except Exception as exc:  # noqa: BLE001 - scenario definition failure is a genuine run failure
        reason = f"[SCENARIO_DEFINITION_ERROR] could not load scenario definition: {exc}"
        await _update_run(
            run_id,
            status="FAILED",
            failure_reason=reason,
            completed_at=datetime.now().astimezone(),
        )
        await _append_timeline(
            run_id,
            reason,
            level="ERROR",
            code="SCENARIO_DEFINITION_ERROR",
        )
        return

    try:
        await _execute(run_id, scenario)
    except Exception as exc:  # noqa: BLE001 - isolate all unexpected failures into this run only
        logger.exception("scenario_run_unhandled_failure run_id=%s scenario_id=%s", run_id, scenario.id)
        reason = str(exc)
        code = _reason_code(reason) or "UNEXPECTED_RUNTIME_ERROR"
        if code == "UNEXPECTED_RUNTIME_ERROR":
            reason = f"[{code}] Demo Control encountered an unexpected runtime error: {reason}"
        await _append_timeline(run_id, reason, level="ERROR", code=code)
        await _update_run(
            run_id,
            status="FAILED",
            failure_reason=reason,
            completed_at=datetime.now().astimezone(),
        )


async def _execute(run_id: str, scenario: ScenarioDefinition) -> None:
    await _update_run(run_id, status="PREPARING", current_step="preconditions")
    await _append_timeline(run_id, "Preparing scenario and validating upstream services")

    try:
        async with httpx.AsyncClient(base_url=settings.missionnet_base_url, timeout=15.0) as mn_client:
            health = await request_json(
                mn_client,
                "GET",
                "/health",
                component="MissionNet",
                retry_safe=True,
                expected_type=dict,
            )
    except UpstreamResponseError as exc:
        await _fail(run_id, str(exc))
        return

    if not health.get("status"):
        await _fail(run_id, "[UPSTREAM_HEALTH_ERROR] MissionNet GET /health returned no status field")
        return

    try:
        async with httpx.AsyncClient(base_url=settings.sentinel_base_url, timeout=15.0) as s_client:
            await request_json(
                s_client,
                "GET",
                "/api/v1/health",
                component="Sentinel API",
                retry_safe=True,
                allow_non_json_success=True,
            )
    except UpstreamResponseError as exc:
        await _fail(run_id, str(exc))
        return

    await _append_timeline(run_id, "MissionNet and Sentinel API health checks passed")

    if scenario.reset.strategy == "lab_reset":
        await _append_timeline(run_id, "Resetting lab to deterministic baseline")
        try:
            await _reset_lab()
        except UpstreamResponseError as exc:
            await _fail(run_id, str(exc))
            return
        await _append_timeline(run_id, "Deterministic lab baseline reset completed")

    try:
        async with httpx.AsyncClient(base_url=settings.missionnet_base_url, timeout=15.0) as mn_client:
            state = await request_json(
                mn_client,
                "GET",
                "/state",
                component="MissionNet",
                retry_safe=True,
                expected_type=dict,
            )
    except UpstreamResponseError as exc:
        await _fail(run_id, str(exc))
        return

    observed_status = state.get("status")
    if observed_status != scenario.preconditions.missionnet_status:
        await _fail(
            run_id,
            "[SCENARIO_PRECONDITION_FAILED] "
            f"expected MissionNet status {scenario.preconditions.missionnet_status!r}, "
            f"got {observed_status!r}",
        )
        return

    run_started_at = datetime.now().astimezone()
    try:
        async with httpx.AsyncClient(base_url=settings.sentinel_base_url, timeout=15.0) as s_client:
            baseline = await capture_baseline(s_client)
    except UpstreamResponseError as exc:
        await _fail(run_id, str(exc))
        return

    await _update_run(run_id, status="RUNNING", current_step="steps")
    await _append_timeline(run_id, "Baseline captured; executing approved scenario actions")
    step_results = []

    async with httpx.AsyncClient(base_url=settings.missionnet_base_url, timeout=15.0) as mn_client:
        for step, target in _expand_steps(scenario.steps):
            if await _is_cancelled(run_id):
                await _finish_cancelled(run_id)
                return

            action_fn = ACTIONS.get(step.action)
            if action_fn is None:
                await _fail(run_id, f"[SCENARIO_ACTION_UNKNOWN] unknown scenario action: {step.action!r}")
                return

            await _update_run(run_id, current_step=step.id)
            await _append_timeline(
                run_id,
                f"Executing {step.action} on {target or 'scenario runtime'}",
                component="MissionNet" if step.action != "run_network_sensor_lab" else "Sensor Lab",
            )
            try:
                parameters_with_provenance = {
                    **step.parameters,
                    "scenario_id": scenario.id,
                    "run_id": run_id,
                    "step_id": step.id,
                }
                response = await action_fn(mn_client, target, parameters_with_provenance)
                step_results.append(
                    {
                        "step_id": step.id,
                        "action": step.action,
                        "target": target,
                        "response": response,
                    }
                )
                await _append_timeline(
                    run_id,
                    f"Completed {step.action} on {target or 'scenario runtime'}",
                    component="MissionNet" if step.action != "run_network_sensor_lab" else "Sensor Lab",
                )
            except ActionError as exc:
                await _fail(run_id, f"step {step.id} ({step.action}) failed: {exc}")
                return

    await _update_run(run_id, step_results=step_results, status="WAITING_FOR_TELEMETRY")
    await _append_timeline(run_id, "Scenario actions completed; waiting for source evidence")

    missionnet_event_ids = await _poll_missionnet_events(run_id, scenario, run_started_at)
    if missionnet_event_ids is None:
        await _fail(
            run_id,
            "[EVIDENCE_TIMEOUT] expected MissionNet event(s) were not observed within the configured timeout",
        )
        return
    await _update_run(run_id, missionnet_event_ids=missionnet_event_ids)
    await _append_timeline(
        run_id,
        f"Observed {len(missionnet_event_ids)} MissionNet source event(s)",
        component="MissionNet",
    )

    await _update_run(run_id, status="WAITING_FOR_SENTINEL")
    await _append_timeline(run_id, "Triggering Sentinel ingestion and deterministic verification")

    verification = await _poll_sentinel_pipeline(run_id, scenario, baseline, run_started_at)
    if verification is None:
        await _fail(
            run_id,
            "[SENTINEL_VERIFICATION_TIMEOUT] Sentinel did not produce the expected detection/incident in time",
        )
        return

    verification.checks["missionnet_event_observed"] = True
    await _append_timeline(run_id, "Sentinel normalized event evidence observed", component="Sentinel API")
    if verification.detection_ids:
        await _append_timeline(
            run_id,
            f"Deterministic detections observed: {len(verification.detection_ids)}",
            component="Sentinel API",
        )
    if verification.incident_ids:
        await _append_timeline(
            run_id,
            f"Incidents observed: {', '.join(verification.incident_ids)}",
            component="Sentinel API",
        )
    await _append_timeline(run_id, "Evidence linkage verification completed", component="Sentinel API")

    await _update_run(run_id, status="VERIFYING")

    passed = verification.all_passed
    failure_reason = None
    if not passed:
        failure_reason = f"[VERIFICATION_FAILED] one or more verification checks failed: {verification.checks}"
    await _update_run(
        run_id,
        status="PASSED" if passed else "FAILED",
        sentinel_event_ids=verification.sentinel_event_ids,
        detection_ids=verification.detection_ids,
        incident_ids=verification.incident_ids,
        verification=verification.checks,
        failure_reason=failure_reason,
        completed_at=datetime.now().astimezone(),
        current_step=None,
    )
    if passed:
        logger.info("scenario_run_passed run_id=%s scenario_id=%s", run_id, scenario.id)
        await _append_timeline(run_id, "Scenario completed successfully", level="INFO", code="RUN_PASSED")
    else:
        logger.error("scenario_run_verification_failed run_id=%s scenario_id=%s", run_id, scenario.id)
        await _append_timeline(
            run_id,
            failure_reason or "Verification failed",
            level="ERROR",
            code="VERIFICATION_FAILED",
        )


async def _poll_missionnet_events(
    run_id: str, scenario: ScenarioDefinition, since: datetime
) -> list[str] | None:
    deadline = asyncio.get_event_loop().time() + settings.poll_timeout_seconds
    expected = scenario.expected_observations.missionnet

    async with httpx.AsyncClient(base_url=settings.missionnet_base_url, timeout=15.0) as mn_client:
        while True:
            if await _is_cancelled(run_id):
                return None
            audit = await request_json(
                mn_client,
                "GET",
                "/audit",
                component="MissionNet",
                retry_safe=True,
                expected_type=list,
                params={"since": since.isoformat(), "limit": 500},
            )
            telemetry = await request_json(
                mn_client,
                "GET",
                "/telemetry",
                component="MissionNet",
                retry_safe=True,
                expected_type=list,
                params={"since": since.isoformat(), "limit": 500},
            )

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
            # Ingestion is idempotent by design. Its response body is not security evidence, so a
            # successful empty/non-JSON 2xx is acceptable; verification reads the real persisted data.
            await request_json(
                s_client,
                "POST",
                "/api/v1/ingest/run",
                component="Sentinel API",
                retry_safe=True,
                allow_non_json_success=True,
            )
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
    code = _reason_code(reason) or "RUN_FAILED"
    logger.error("scenario_run_failed run_id=%s code=%s reason=%s", run_id, code, reason)
    await _append_timeline(run_id, reason, level="ERROR", code=code)
    await _update_run(
        run_id,
        status="FAILED",
        failure_reason=reason,
        completed_at=datetime.now().astimezone(),
    )


async def _finish_cancelled(run_id: str) -> None:
    logger.info("scenario_run_cancelled run_id=%s", run_id)
    await _append_timeline(run_id, "Scenario cancelled by operator", level="WARN", code="RUN_CANCELLED")
    await _update_run(run_id, status="CANCELLED", completed_at=datetime.now().astimezone())


async def reset_after_run(run_id: str) -> None:
    run = await _load_run(run_id)
    if run is None:
        raise ValueError(f"scenario run {run_id} not found")
    try:
        await _reset_lab()
        await _update_run(run_id, reset_status="RESET_COMPLETE")
        await _append_timeline(run_id, "Lab reset completed", code="RESET_COMPLETE")
    except UpstreamResponseError as exc:
        await _update_run(run_id, reset_status=f"RESET_FAILED: {exc}")
        await _append_timeline(
            run_id,
            str(exc),
            level="ERROR",
            code=exc.code,
            component=exc.component,
        )
        raise
