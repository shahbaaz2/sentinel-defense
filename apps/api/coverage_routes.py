"""Detection coverage (blueprint §16.6). Static "which rule does what" comes straight from the
rule catalog (services/detection_engine/rules.py); "has this rule ever been validated by a
scenario" comes from Demo Control's run history over HTTP - Sentinel doesn't import Demo Control's
code, and if Demo Control is unreachable every rule just reports NOT_TESTED rather than crashing
(the same graceful-degradation pattern used elsewhere - see DECISIONS.md).
"""

import logging
from typing import Literal

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.schemas import RuleCoverageOut
from domain.db import get_session
from domain.models.orm import Detection
from services.detection_engine.rules import RULES

logger = logging.getLogger("sentinel.coverage")
router = APIRouter(prefix="/api/v1")
DEMO_CONTROL_BASE_URL = "http://127.0.0.1:8100"


async def _scenario_rule_map() -> dict[str, list[str]]:
    """rule_id -> [scenario_id, ...] that expect it, read from Demo Control's own scenario
    definitions (static content - the scenario YAML doesn't change at runtime)."""
    rule_to_scenarios: dict[str, list[str]] = {}
    try:
        async with httpx.AsyncClient(base_url=DEMO_CONTROL_BASE_URL, timeout=3.0) as client:
            summaries = (await client.get("/api/v1/scenarios")).json()
            for summary in summaries:
                detail = (await client.get(f"/api/v1/scenarios/{summary['id']}")).json()
                for expectation in detail.get("expected_observations", {}).get("sentinel", {}).get(
                    "detections", []
                ):
                    rule_to_scenarios.setdefault(expectation["rule_id"], []).append(summary["id"])
    except httpx.HTTPError:
        logger.warning("Demo Control unreachable - scenario coverage mapping unavailable")
    return rule_to_scenarios


async def _scenario_pass_fail() -> dict[str, set[str]]:
    """scenario_id -> {"PASSED", "FAILED"} statuses ever observed for it, from Demo Control's run
    history."""
    outcomes: dict[str, set[str]] = {}
    try:
        async with httpx.AsyncClient(base_url=DEMO_CONTROL_BASE_URL, timeout=3.0) as client:
            runs = (await client.get("/api/v1/runs", params={"limit": 200})).json()
            for run in runs:
                if run["status"] in ("PASSED", "FAILED"):
                    outcomes.setdefault(run["scenario_id"], set()).add(run["status"])
    except httpx.HTTPError:
        logger.warning("Demo Control unreachable - scenario run history unavailable")
    return outcomes


def _validation_status(
    scenario_ids: list[str], outcomes: dict[str, set[str]]
) -> Literal["VALIDATED", "FAILED", "NOT_TESTED"]:
    if not scenario_ids:
        return "NOT_TESTED"
    observed = set()
    for sid in scenario_ids:
        observed |= outcomes.get(sid, set())
    if "PASSED" in observed:
        return "VALIDATED"
    if "FAILED" in observed:
        return "FAILED"
    return "NOT_TESTED"


@router.get("/detection-coverage", response_model=list[RuleCoverageOut])
async def detection_coverage(session: AsyncSession = Depends(get_session)):
    rule_to_scenarios = await _scenario_rule_map()
    outcomes = await _scenario_pass_fail()

    stats_result = await session.execute(
        select(
            Detection.rule_id,
            func.count(Detection.detection_id),
            func.max(Detection.timestamp),
        ).group_by(Detection.rule_id)
    )
    stats = {row[0]: (row[1], row[2]) for row in stats_result.all()}

    out = []
    for rule in RULES:
        total_detections, last_triggered = stats.get(rule.rule_id, (0, None))
        validating_scenarios = rule_to_scenarios.get(rule.rule_id, [])
        out.append(
            RuleCoverageOut(
                rule_id=rule.rule_id,
                name=rule.name,
                version=rule.version,
                enabled=True,
                severity=rule.default_severity,
                category=rule.category,
                description=rule.description,
                event_categories=rule.event_categories,
                mitre_techniques=rule.mitre_techniques,
                validating_scenarios=validating_scenarios,
                validation_status=_validation_status(validating_scenarios, outcomes),
                last_triggered=last_triggered,
                total_detections=total_detections,
            )
        )
    return out
