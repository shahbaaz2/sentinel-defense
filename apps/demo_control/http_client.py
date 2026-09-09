"""Reliable HTTP boundary for Demo Control upstream service calls.

The demo must fail truthfully and diagnostically when MissionNet/Sentinel or a cloud gateway
returns a transient, empty, non-JSON, or application-error response. This module centralizes
that behavior so callers never leak raw JSON decoder exceptions such as
"Expecting value: line 1 column 1" to an operator.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger("demo_control.http")

TRANSIENT_STATUS_CODES = {502, 503, 504}
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.5
ERROR_DETAIL_LIMIT = 300


class UpstreamResponseError(Exception):
    """A classified upstream/integration failure safe to persist and display to an operator."""

    def __init__(
        self,
        *,
        code: str,
        component: str,
        operation: str,
        message: str,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        self.code = code
        self.component = component
        self.operation = operation
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(f"[{code}] {component} {operation}: {message}")


def short_detail(resp: httpx.Response) -> str:
    text = resp.text.strip().replace("\n", " ")
    if len(text) > ERROR_DETAIL_LIMIT:
        return text[:ERROR_DETAIL_LIMIT] + "…"
    return text


def _success_metadata(resp: httpx.Response) -> dict[str, Any]:
    return {
        "accepted": True,
        "http_status": resp.status_code,
        "response_format": "empty" if not resp.content else "non-json",
    }


def _log_failure(error: UpstreamResponseError, attempt: int) -> None:
    logger.warning(
        "upstream_request_failed code=%s component=%s operation=%s status=%s retryable=%s attempt=%s detail=%s",
        error.code,
        error.component,
        error.operation,
        error.status_code,
        error.retryable,
        attempt,
        str(error),
    )


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    component: str,
    retry_safe: bool = False,
    allow_non_json_success: bool = False,
    expected_type: type | tuple[type, ...] | None = None,
    **kwargs: Any,
) -> Any:
    """Execute an upstream request with bounded, explicit reliability semantics.

    Only requests the caller marks ``retry_safe`` are retried. 502/503/504, transport failures,
    and invalid/empty successful responses can be retried because those are common cloud-edge
    failure modes. 4xx and ordinary 5xx application errors are never retried into a fake success.

    For side-effecting actions where the response body is not part of the security evidence,
    ``allow_non_json_success`` accepts a successful 2xx with an empty/non-JSON body and returns
    response metadata. The later evidence-verification stage still decides whether the action
    actually produced the expected observable result.
    """

    method_upper = method.upper()
    operation = f"{method_upper} {path}"
    attempts = MAX_ATTEMPTS if retry_safe else 1

    for attempt in range(1, attempts + 1):
        try:
            resp = await client.request(method_upper, path, **kwargs)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            error = UpstreamResponseError(
                code="UPSTREAM_TRANSPORT_ERROR",
                component=component,
                operation=operation,
                message=f"network/transport failure on attempt {attempt}: {exc}",
                retryable=retry_safe,
            )
            _log_failure(error, attempt)
            if retry_safe and attempt < attempts:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise error from exc

        if resp.status_code in TRANSIENT_STATUS_CODES:
            error = UpstreamResponseError(
                code="UPSTREAM_GATEWAY_ERROR",
                component=component,
                operation=operation,
                message=f"HTTP {resp.status_code} from the cloud gateway",
                status_code=resp.status_code,
                retryable=retry_safe,
            )
            _log_failure(error, attempt)
            if retry_safe and attempt < attempts:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise error

        if resp.status_code >= 400:
            error = UpstreamResponseError(
                code="UPSTREAM_HTTP_ERROR",
                component=component,
                operation=operation,
                message=f"HTTP {resp.status_code}: {short_detail(resp) or 'no response body'}",
                status_code=resp.status_code,
                retryable=False,
            )
            _log_failure(error, attempt)
            raise error

        if not resp.content:
            if allow_non_json_success:
                return _success_metadata(resp)
            error = UpstreamResponseError(
                code="UPSTREAM_INVALID_RESPONSE",
                component=component,
                operation=operation,
                message=f"HTTP {resp.status_code} returned an empty response where JSON was required",
                status_code=resp.status_code,
                retryable=retry_safe,
            )
            _log_failure(error, attempt)
            if retry_safe and attempt < attempts:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise error

        try:
            body = resp.json()
        except ValueError as exc:
            if allow_non_json_success:
                return _success_metadata(resp)
            content_type = resp.headers.get("content-type", "unknown")
            error = UpstreamResponseError(
                code="UPSTREAM_INVALID_RESPONSE",
                component=component,
                operation=operation,
                message=(
                    f"HTTP {resp.status_code} returned non-JSON content ({content_type}); "
                    "the run stopped safely instead of guessing"
                ),
                status_code=resp.status_code,
                retryable=retry_safe,
            )
            _log_failure(error, attempt)
            if retry_safe and attempt < attempts:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise error from exc

        if expected_type is not None and not isinstance(body, expected_type):
            expected_name = getattr(expected_type, "__name__", str(expected_type))
            error = UpstreamResponseError(
                code="UPSTREAM_INVALID_RESPONSE",
                component=component,
                operation=operation,
                message=(
                    f"HTTP {resp.status_code} returned JSON with unexpected type "
                    f"{type(body).__name__}; expected {expected_name}"
                ),
                status_code=resp.status_code,
                retryable=retry_safe,
            )
            _log_failure(error, attempt)
            if retry_safe and attempt < attempts:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            raise error

        return body

    raise AssertionError("request_json exhausted attempts without returning or raising")
