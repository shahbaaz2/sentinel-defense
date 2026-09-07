"""Strict target resolution (blueprint Phase 7 §5). Every target comes from trusted, already-
persisted incident/plan context - never from AI output, never from a raw string an operator types
in. A target that cannot be resolved from real data means the action is either skipped (if not
`required`) or blocks execution entirely (if `required`) - see `executor.py`.
"""

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domain.models.orm import ActionResult, Incident, IncidentEventLink, NormalizedEventRecord
from services.policy_engine.actions import ACTION_REGISTRY
from services.policy_engine.playbooks import PlaybookAction
from services.response_executor.models import ResolvedTarget


async def _first_incident_user_id(session: AsyncSession, incident_id: str) -> str | None:
    """The ground truth for "which identity is this incident about" - the first (earliest) real,
    non-null `user_id` among the incident's own linked evidence events. Deliberately reads
    `NormalizedEventRecord` directly rather than reusing the AI Analyst's curated EvidencePack,
    since the executor is not bound by that pack's "compact enough for a prompt" constraint and
    must not depend on anything the AI layer builds."""
    stmt = (
        select(NormalizedEventRecord.user_id)
        .join(IncidentEventLink, IncidentEventLink.event_id == NormalizedEventRecord.event_id)
        .where(
            IncidentEventLink.incident_id == incident_id,
            NormalizedEventRecord.user_id.is_not(None),
        )
        .order_by(NormalizedEventRecord.timestamp)
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    return row[0] if row else None


async def _first_valid_token_for_user(client: httpx.AsyncClient, user_id: str) -> str | None:
    """Reads MissionNet's public (non-lab) `/identity/tokens` list - a plain state read, not a
    lab-control mutation. Prefers a still-valid token; falls back to any token the identity owns
    (revoking an already-revoked token is a harmless idempotent no-op)."""
    resp = await client.get("/identity/tokens")
    resp.raise_for_status()
    tokens = [t for t in resp.json() if t["owner_user_id"] == user_id]
    if not tokens:
        return None
    valid = [t for t in tokens if t["valid"]]
    chosen = valid[0] if valid else tokens[0]
    return chosen["token_id"]


async def resolve_target(
    *,
    action: PlaybookAction,
    action_index: int,
    session: AsyncSession,
    incident: Incident,
    client: httpx.AsyncClient,
    prior_results: dict[int, ActionResult],
) -> ResolvedTarget | None:
    """Returns None if no real target can be resolved - the caller decides whether that blocks
    execution (required) or is a no-op (not required)."""
    if action.target_source == "incident":
        return ResolvedTarget(target_type="incident", target_id=incident.incident_id)

    if action.target_source == "incident_asset":
        asset_id = incident.primary_asset_id
        if asset_id is None:
            return None
        # Special case: verify_service_health run after a request_replacement_instance step in
        # the same plan should check the *replacement*, not the original (deliberately still-
        # quarantined) asset - see docs/response-executor.md.
        if action.action_id == "verify_service_health":
            for result in prior_results.values():
                if (
                    result.action_id == "request_replacement_instance"
                    and result.status == "SUCCEEDED"
                    and "replacement_asset_id" in result.result_metadata
                ):
                    asset_id = result.result_metadata["replacement_asset_id"]
        return ResolvedTarget(target_type="asset", target_id=asset_id)

    if action.target_source == "incident_identity":
        user_id = await _first_incident_user_id(session, incident.incident_id)
        if user_id is None:
            return None
        action_def = ACTION_REGISTRY[action.action_id]
        if "service_token" in action_def.allowed_target_types:
            token_id = await _first_valid_token_for_user(client, user_id)
            if token_id is None:
                return None
            return ResolvedTarget(target_type="service_token", target_id=token_id)
        return ResolvedTarget(target_type="identity_user", target_id=user_id)

    return None
