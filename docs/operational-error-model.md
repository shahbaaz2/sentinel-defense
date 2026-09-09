# Sentinel Operational Error Model

Sentinel separates **core security workflow state** from **external dependency state**. A provider, gateway, or cloud-runtime failure must never be presented as if a deterministic detection or incident failed when the underlying security pipeline is still valid.

## Operator-facing principles

1. **Classify before displaying.** Raw decoder exceptions, proxy HTML, stack traces, and provider response bodies are not operator messages.
2. **Identify the affected component.** Demo Control, MissionNet, Sentinel Core, Sensor Lab, and AI Advisory are separate operational dependencies.
3. **State impact precisely.** A stopped scenario run is not advanced past the last observed stage. An AI advisory failure does not invalidate deterministic incident evidence.
4. **Provide a next action.** Every failure category should tell the operator whether to retry, review a service log, restore a baseline, or correct an external provider issue.
5. **Preserve evidence integrity.** No UI component marks a stage passed without observed backend evidence.

## Demo Control upstream error codes

| Code | Meaning | Retry behavior | Operator interpretation |
| --- | --- | --- | --- |
| `UPSTREAM_TRANSPORT_ERROR` | Connection/timeout failure to MissionNet or Sentinel | Bounded retry only when the operation is explicitly replay-safe | Cloud/service connectivity problem |
| `UPSTREAM_GATEWAY_ERROR` | HTTP 502/503/504 from an upstream gateway | Bounded retry only when replay-safe | Temporary hosting/gateway interruption |
| `UPSTREAM_HTTP_ERROR` | Application-level HTTP error | No automatic retry | Upstream application rejected or failed the operation |
| `UPSTREAM_INVALID_RESPONSE` | Empty, non-JSON, or unexpected JSON response where structured JSON is required | Bounded retry only when replay-safe | Integration contract failure; never expose a JSON decoder exception |
| `UPSTREAM_HEALTH_ERROR` | Health response did not satisfy the expected contract | No fabricated health state | Dependency health cannot be trusted |
| `SCENARIO_PRECONDITION_FAILED` | Synthetic environment is not at the required baseline | No automatic scenario continuation | Reset/reconcile lab state first |
| `EVIDENCE_TIMEOUT` | Expected source evidence was not observed in time | Run fails | Investigate source telemetry path |
| `SENTINEL_VERIFICATION_TIMEOUT` | Expected Sentinel detection/incident was not observed in time | Run fails | Investigate ingestion/detection/correlation path |
| `VERIFICATION_FAILED` | One or more evidence-integrity controls failed | Run fails | Review the verification checklist |

## AI advisory provider codes

The AI Analyst is an **advisory dependency**, not a detection authority. These errors are persisted and displayed independently from Sentinel Core.

| Code | Meaning | Sentinel Core impact |
| --- | --- | --- |
| `AI_PROVIDER_BILLING` | Configured DeepSeek account has insufficient API balance | None |
| `AI_PROVIDER_AUTH` | Provider credential rejected | None |
| `AI_PROVIDER_RATE_LIMIT` | Provider rate limit reached | None |
| `AI_PROVIDER_UPSTREAM` | Provider service temporarily unavailable | None |
| `AI_PROVIDER_NETWORK` | Network request to provider failed | None |
| `AI_PROVIDER_TIMEOUT` | Advisory request exceeded configured timeout | None |
| `AI_PROVIDER_INVALID_RESPONSE` | Provider API response was not valid structured API data | None |
| `AI_PROVIDER_INVALID_OUTPUT` | Model output failed Sentinel's required assessment schema | None; invalid output is rejected |
| `AI_PROVIDER_CONFIG` | Provider is not configured | None |

For DeepSeek deployments, provider status uses `GET /user/balance` as a no-inference availability check. If the provider reports that the account is unavailable for API calls, the UI reports an AI billing dependency issue instead of a Sentinel system failure.

## Structured run log

Demo Control persists timeline entries with the following operator fields:

```json
{
  "timestamp": "2026-09-09T12:00:00-05:00",
  "level": "ERROR",
  "component": "MissionNet",
  "code": "UPSTREAM_INVALID_RESPONSE",
  "message": "[UPSTREAM_INVALID_RESPONSE] MissionNet GET /state: HTTP 200 returned non-JSON content..."
}
```

The GUI renders these fields as an operational table. The raw timeline remains part of the run record for later review.

## UI behavior

- **Scenario Execution Console:** shows actual backend-derived stages only; no cinematic progression or simulated success.
- **Run Detail:** shows run status, structured operational log, observed evidence counts, verification controls, and classified failure diagnostics.
- **AI Analyst:** shows provider/model status separately from Sentinel Core. Billing/auth/rate-limit/provider outages are clearly labeled as external AI advisory issues.
- **Demo Control home:** reports MissionNet, Sentinel Core, and AI Advisory as separate dependencies.

## Reliability boundary

Automatic retry is intentionally narrow. A retry is only used where the operation is known to be safe to replay or idempotent. Real 4xx application failures and ordinary application 500 errors are not retried into apparent success.
