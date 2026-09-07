"""Thin, real-shaped Splunk REST client. Read-only: the only two endpoints ever called are
`/services/server/info` (health) and `/services/search/jobs/export` (a one-shot, streaming, bounded
search) - never anything that writes to Splunk. TLS verification defaults on; the token is sent
only as an Authorization header and is never logged (see `_redact_repr__` below) or returned to a
frontend - see docs/splunk-integration.md.
"""

import json

import httpx

from integrations.splunk.schemas import SplunkSearchRequest, SplunkServerInfo

DEFAULT_TIMEOUT_SECONDS = 15.0


class SplunkAuthError(RuntimeError):
    """401/403 from Splunk - the token is missing, expired, or lacks search capability."""


class SplunkTimeoutError(RuntimeError):
    """The search or health check did not complete within the configured timeout."""


class SplunkClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        verify_tls: bool = True,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._verify_tls = verify_tls
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def __repr__(self) -> str:
        # Never let a stray `repr(client)` in a log line or traceback leak the token.
        return f"SplunkClient(base_url={self._base_url!r}, token=***redacted***)"

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
            verify=self._verify_tls,
            transport=self._transport,
            headers={"Authorization": f"Bearer {self._token}"},
        )

    async def health(self) -> SplunkServerInfo | None:
        try:
            async with self._client() as client:
                resp = await client.get(
                    "/services/server/info", params={"output_mode": "json"}
                )
        except httpx.TimeoutException:
            return None
        except httpx.HTTPError:
            return None
        if resp.status_code in (401, 403):
            return None
        if resp.status_code != 200:
            return None
        body = resp.json()
        entry = (body.get("entry") or [{}])[0].get("content", {})
        return SplunkServerInfo(
            version=entry.get("version"), server_name=entry.get("serverName")
        )

    async def search(self, request: SplunkSearchRequest) -> list[dict]:
        """Runs a bounded, read-only search via the `/search/jobs/export` one-shot streaming
        endpoint - no job-polling needed, and Splunk itself enforces `count` as a hard result cap
        so a broad query can never return an unbounded response."""
        already_prefixed = request.query.strip().startswith("search")
        query = request.query if already_prefixed else f"search {request.query}"
        params = {
            "search": query,
            "earliest_time": request.earliest_time,
            "latest_time": request.latest_time,
            "count": request.count,
            "output_mode": "json",
        }
        try:
            async with self._client() as client:
                resp = await client.post("/services/search/jobs/export", data=params)
        except httpx.TimeoutException as exc:
            raise SplunkTimeoutError(str(exc)) from exc

        if resp.status_code in (401, 403):
            raise SplunkAuthError(f"Splunk rejected the configured token (HTTP {resp.status_code})")
        resp.raise_for_status()

        results = []
        for line in resp.text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            result = record.get("result")
            if result is not None:
                results.append(result)
        return results[: request.count]
