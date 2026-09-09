"""Unit tests for Demo Control's bounded record-access retry (apps/demo_control/actions.py) -
`httpx.MockTransport`, no live MissionNet required. Covers exactly the reliability contract: retry
only transient gateway/transport failures, never a real application error, never fabricate
success, and never let a raw HTML error page reach an ActionError message unbounded.
"""

import httpx
import pytest

from apps.demo_control.actions import (
    ActionError,
    _get_with_bounded_retry,
    _short_detail,
    access_record,
)


def _client(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="http://missionnet.test")


async def test_succeeds_immediately_on_first_try():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json={"record_id": "rec-000"})

    async with _client(handler) as client:
        result = await _get_with_bounded_retry(client, "/mission-data/records/rec-000")
    assert result == {"record_id": "rec-000"}
    assert calls["count"] == 1


@pytest.mark.parametrize("status", [502, 503, 504])
async def test_retries_transient_gateway_statuses_then_succeeds(status):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 3:
            return httpx.Response(status, text="<html>Bad Gateway</html>")
        return httpx.Response(200, json={"record_id": "rec-000"})

    async with _client(handler) as client:
        result = await _get_with_bounded_retry(client, "/mission-data/records/rec-000")
    assert result == {"record_id": "rec-000"}
    assert calls["count"] == 3


async def test_gives_up_after_max_attempts_and_raises_action_error():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(502, text="<html>Bad Gateway</html>")

    async with _client(handler) as client:
        with pytest.raises(ActionError):
            await _get_with_bounded_retry(client, "/mission-data/records/rec-000")
    assert calls["count"] == 3  # exactly _MAX_ATTEMPTS, never more, never fewer


async def test_never_retries_a_real_4xx_application_error():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(404, text="mission record not found")

    async with _client(handler) as client:
        with pytest.raises(ActionError):
            await _get_with_bounded_retry(client, "/mission-data/records/rec-999")
    assert calls["count"] == 1  # no retry - a 4xx is a real error, not transient


async def test_retries_transport_level_failures():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] < 2:
            raise httpx.ConnectError("connection reset")
        return httpx.Response(200, json={"record_id": "rec-000"})

    async with _client(handler) as client:
        result = await _get_with_bounded_retry(client, "/mission-data/records/rec-000")
    assert result == {"record_id": "rec-000"}
    assert calls["count"] == 2


async def test_never_converts_a_persistent_transport_failure_into_success():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async with _client(handler) as client:
        with pytest.raises(ActionError):
            await _get_with_bounded_retry(client, "/mission-data/records/rec-000")


def test_short_detail_truncates_a_large_html_error_page():
    huge_html = "<html>" + ("body " * 500) + "</html>"
    resp = httpx.Response(502, text=huge_html)
    detail = _short_detail(resp)
    assert len(detail) <= 301  # limit + ellipsis
    assert "\n" not in detail


def test_short_detail_leaves_a_short_message_untouched():
    resp = httpx.Response(404, text="mission record not found")
    assert _short_detail(resp) == "mission record not found"


async def test_access_record_forwards_run_and_step_id_as_query_params():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return httpx.Response(200, json={"record_id": "rec-000"})

    async with _client(handler) as client:
        await access_record(
            client,
            "rec-000",
            {"actor_user_id": "svc-mission-data-01", "scenario_id": "SCN-010",
             "run_id": "RUN-abc", "step_id": "step-3"},
        )
    assert captured["params"]["run_id"] == "RUN-abc"
    assert captured["params"]["step_id"] == "step-3"
    assert captured["params"]["actor_user_id"] == "svc-mission-data-01"


async def test_access_record_works_without_run_id_step_id_backward_compatible():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "run_id" not in request.url.params
        assert "step_id" not in request.url.params
        return httpx.Response(200, json={"record_id": "rec-000"})

    async with _client(handler) as client:
        result = await access_record(client, "rec-000", {"actor_user_id": "u-analyst-01"})
    assert result == {"record_id": "rec-000"}
