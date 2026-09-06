"""Phase 4: incident case-management workflow (status/assignment/notes/disposition) and the audit
trail every change must produce. Requires the real live stack (Postgres + MissionNet + Sentinel +
Demo Control) - a scenario run is the simplest way to get a genuine incident to operate on.
"""

import asyncio

import httpx
import pytest

from apps.missionnet.seed import reset_and_seed as reset_missionnet
from services.event_ingestor.reset import reset as reset_sentinel

pytestmark = pytest.mark.integration

SENTINEL_BASE_URL = "http://127.0.0.1:8080"
DEMO_CONTROL_BASE_URL = "http://127.0.0.1:8100"
TERMINAL_RUN_STATES = {"PASSED", "FAILED", "CANCELLED"}


@pytest.fixture(autouse=True)
async def _reset_everything():
    await reset_missionnet()
    await reset_sentinel()
    yield
    await reset_missionnet()
    await reset_sentinel()


async def _sentinel_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=SENTINEL_BASE_URL, timeout=15.0)


async def _run_scn003_and_get_incident_id() -> str:
    async with httpx.AsyncClient(base_url=DEMO_CONTROL_BASE_URL, timeout=15.0) as dc:
        resp = await dc.post("/api/v1/scenarios/SCN-003/run", json={})
        run_id = resp.json()["run_id"]

        deadline = asyncio.get_event_loop().time() + 30.0
        while True:
            run = (await dc.get(f"/api/v1/runs/{run_id}")).json()
            if run["status"] in TERMINAL_RUN_STATES:
                break
            if asyncio.get_event_loop().time() >= deadline:
                raise AssertionError(f"run did not finish in time: {run}")
            await asyncio.sleep(0.5)

    assert run["status"] == "PASSED", run.get("failure_reason")
    return run["incident_ids"][0]


async def test_status_transition_persists_and_is_audited():
    incident_id = await _run_scn003_and_get_incident_id()

    async with await _sentinel_client() as sentinel:
        resp = await sentinel.patch(
            f"/api/v1/incidents/{incident_id}/status",
            json={"status": "INVESTIGATING", "actor": "j.analyst"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "INVESTIGATING"

        detail = (await sentinel.get(f"/api/v1/incidents/{incident_id}")).json()
        assert detail["status"] == "INVESTIGATING"

        audit = (
            await sentinel.get("/api/v1/audit", params={"entity_id": incident_id})
        ).json()
    matching = [a for a in audit if a["action"] == "incident.status_changed"]
    assert len(matching) == 1
    assert matching[0]["actor"] == "j.analyst"
    assert matching[0]["detail"] == {"old_status": "OPEN", "new_status": "INVESTIGATING"}


async def test_invalid_status_value_rejected():
    incident_id = await _run_scn003_and_get_incident_id()
    async with await _sentinel_client() as sentinel:
        resp = await sentinel.patch(
            f"/api/v1/incidents/{incident_id}/status", json={"status": "NOT_A_REAL_STATUS"}
        )
    assert resp.status_code == 422


async def test_resolving_sets_resolved_at_and_unresolving_clears_it():
    incident_id = await _run_scn003_and_get_incident_id()
    async with await _sentinel_client() as sentinel:
        resolved = await sentinel.patch(
            f"/api/v1/incidents/{incident_id}/status", json={"status": "RESOLVED"}
        )
        assert resolved.json()["resolved_at"] is not None

        reopened = await sentinel.patch(
            f"/api/v1/incidents/{incident_id}/status", json={"status": "OPEN"}
        )
        assert reopened.json()["resolved_at"] is None


async def test_assignment_persists_and_is_audited():
    incident_id = await _run_scn003_and_get_incident_id()
    async with await _sentinel_client() as sentinel:
        resp = await sentinel.patch(
            f"/api/v1/incidents/{incident_id}/assignment",
            json={"assigned_to": "j.analyst", "actor": "j.analyst"},
        )
        assert resp.json()["assigned_to"] == "j.analyst"

        audit = (
            await sentinel.get(
                "/api/v1/audit", params={"entity_id": incident_id, "action": "incident.assigned"}
            )
        ).json()
    assert len(audit) == 1


async def test_notes_are_additive_and_audited():
    incident_id = await _run_scn003_and_get_incident_id()
    async with await _sentinel_client() as sentinel:
        first = await sentinel.post(
            f"/api/v1/incidents/{incident_id}/notes",
            json={"author": "j.analyst", "body": "First note."},
        )
        assert first.status_code == 200
        second = await sentinel.post(
            f"/api/v1/incidents/{incident_id}/notes",
            json={"author": "m.osei", "body": "Second note, different analyst."},
        )
        assert second.status_code == 200

        notes = (await sentinel.get(f"/api/v1/incidents/{incident_id}/notes")).json()
        assert [n["body"] for n in notes] == ["First note.", "Second note, different analyst."]

        detail = (await sentinel.get(f"/api/v1/incidents/{incident_id}")).json()
        assert len(detail["notes"]) == 2

        audit = (
            await sentinel.get(
                "/api/v1/audit",
                params={"entity_id": incident_id, "action": "incident.note_added"},
            )
        ).json()
    assert len(audit) == 2


async def test_empty_note_body_rejected():
    incident_id = await _run_scn003_and_get_incident_id()
    async with await _sentinel_client() as sentinel:
        resp = await sentinel.post(
            f"/api/v1/incidents/{incident_id}/notes", json={"author": "j.analyst", "body": ""}
        )
    assert resp.status_code == 422


async def test_disposition_update_persists_and_is_audited():
    incident_id = await _run_scn003_and_get_incident_id()
    async with await _sentinel_client() as sentinel:
        resp = await sentinel.patch(
            f"/api/v1/incidents/{incident_id}/disposition",
            json={"disposition": "TEST_SCENARIO", "actor": "j.analyst"},
        )
        assert resp.json()["disposition"] == "TEST_SCENARIO"

        invalid = await sentinel.patch(
            f"/api/v1/incidents/{incident_id}/disposition", json={"disposition": "NOT_REAL"}
        )
        assert invalid.status_code == 422

        audit = (
            await sentinel.get(
                "/api/v1/audit",
                params={"entity_id": incident_id, "action": "incident.disposition_set"},
            )
        ).json()
    assert len(audit) == 1


async def test_incident_carries_real_scenario_provenance():
    """Proves the Phase 4 provenance fix: an incident created by a Demo Control scenario run
    genuinely carries that scenario's ID, not a null/placeholder value."""
    incident_id = await _run_scn003_and_get_incident_id()
    async with await _sentinel_client() as sentinel:
        detail = (await sentinel.get(f"/api/v1/incidents/{incident_id}")).json()
    assert detail["scenario_id"] == "SCN-003"


async def test_workflow_actions_on_unknown_incident_404():
    async with await _sentinel_client() as sentinel:
        status_resp = await sentinel.patch(
            "/api/v1/incidents/INC-does-not-exist/status", json={"status": "OPEN"}
        )
        note_resp = await sentinel.post(
            "/api/v1/incidents/INC-does-not-exist/notes",
            json={"author": "x", "body": "y"},
        )
    assert status_resp.status_code == 404
    assert note_resp.status_code == 404
