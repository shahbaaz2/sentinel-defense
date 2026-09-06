# PROGRESS

Current phase, what is actually verified working (not just present), and the next task. Update this at
every phase checkpoint — never claim something works without having run the check.

## Current phase: Phase 0 — COMPLETE (all acceptance criteria verified)

### Verified working (commands actually run, not assumed)
- Mac inspected: arm64, macOS 15.3.1, 16 GB RAM, 8 cores → **Lite profile** (DECISIONS.md).
- Homebrew tools installed and version-checked: node v26.8.1, pnpm 11.25.0, colima 0.10.3,
  docker 29.8.0, docker-compose 5.5.1 (standalone binary — `docker compose` v2 plugin is not wired up
  on this machine; scripts use `docker-compose` instead, documented in RUNBOOK.md), uv 0.12.10,
  jq 1.8.2, python3.12 via Homebrew.
- Repo structure created per blueprint §6; `DECISIONS.md` written with the mandatory three-deliverable
  decomposition before any code.
- Python venv (`.venv`, Python 3.12) created via `scripts/bootstrap-mac.sh`; all dev dependencies
  installed (FastAPI, Pydantic v2, SQLAlchemy async, asyncpg, Alembic, pytest, ruff, mypy).
- `domain/models/events.py`: `NormalizedEvent` Pydantic model per blueprint §8, with field bounds
  (max lengths on strings/lists) to prevent prompt-injection payload bloat. 13 unit tests pass,
  covering valid construction, immutability, enum/range rejection, and oversized-field rejection.
  Run: `.venv/bin/pytest -q` → **13 passed**.
- `domain/repositories/__init__.py`: `EventRepository` Protocol — the dependency-inversion seam so
  services never import a vendor SDK directly (blueprint §6.1).
- `apps/api` (Sentinel FastAPI): `/api/v1/health`, `/api/v1/system/profile`,
  `/api/v1/system/assurance`. Started on :8080 and hit with curl — all three return correct JSON,
  including `external_ai_api: disabled` (verified, not assumed).
- `apps/missionnet` (MissionNet FastAPI shell): `/health` returns
  `{"status": "nominal", "classification": "SYNTHETIC", ...}`. Started on :8090, curl-verified.
- `apps/dashboard` (Sentinel dashboard, Next.js 16 + Tailwind): server-rendered page fetches
  `/api/v1/system/assurance` from the API and renders the Deployment Assurance panel live. Started on
  :3000, verified both via curl (HTML contains the live values) and a browser screenshot.
- `apps/missionnet-console` (MissionNet Operations Console shell, Next.js 16 + Tailwind): fetches
  MissionNet's `/health` and renders it live. Started on :3100, curl + screenshot verified.
- `pnpm exec tsc --noEmit` clean on both frontend apps. `.venv/bin/ruff check .` clean on the backend.
- PostgreSQL running in Colima (`infrastructure/compose/docker-compose.yml`, `pgvector/pgvector:pg16`
  image) with two databases/roles created by `infrastructure/compose/init-db.sql`: `sentinel` and
  `missionnet`, both with the `vector` extension installed. Verified with
  `docker exec sentinel-postgres psql ... \dx` and `\l`.
- `scripts/healthcheck.sh` run end-to-end with everything up: **all checks PASS** except the local
  model endpoint (correctly WARN/non-critical — Phase 5 hasn't started).

### Known fix applied during Phase 0 (recorded so it isn't rediscovered)
- `docker compose` (v2 subcommand) isn't available on this machine even with `docker` and
  `docker-compose` both installed via Homebrew — the plugin isn't symlinked into
  `~/.docker/cli-plugins/`. Scripts use the standalone `docker-compose` binary instead. See RUNBOOK.md.
- `~/.docker/config.json` had `"credsStore": "desktop"` pointing at a Docker-Desktop-only credential
  helper that doesn't exist under Colima, which broke anonymous image pulls. Removed that key (backed
  up to `~/.docker/config.json.bak`) since this project doesn't use private registries.

### Phase 0 acceptance criteria (blueprint §26) — all met
- [x] `make dev-up`, `make health`, and `make test` pass.
- [x] Sentinel shell, MissionNet shell, and API health endpoints are reachable.
- [x] No paid cloud/API dependency (LLM provider is `mock`, external AI explicitly disabled).

### Next task
Begin **Phase 1 — MissionNet as a real synthetic application**: Identity Service, Mission Data API,
Telemetry Gateway, Asset Registry, deterministic seed dataset, audit events, and the internal
`/lab/*` control API. Acceptance target: MissionNet runs independently from Sentinel, the console shows
seeded synthetic assets/services with real backend health state, `make reset-lab` restores the exact
seed baseline, and at least one state change (e.g. a synthetic token revoke) is visibly reflected in
both the UI and the audit stream.

## Phase acceptance status

| Phase | Acceptance criteria met? |
|---|---|
| 0 — Repo/bootstrap/contracts | **Yes — verified** |
| 1 — MissionNet real app | Not started |
| 2 — Sentinel event/detection/incident | Not started |
| 3 — Demo Control + SCN-010 causality | Not started |
| 4 — Sentinel dashboard | Not started |
| 5 — Local AI analyst + RAG | Not started |
| 6 — Playbooks/policy/approval | Not started |
| 7 — Deterministic response + verification (MVP stopping point) | Not started |
| 8 — Real sensors + SIEM portability | Not started |
| 9 — Validation/coverage/offline hardening | Not started |
| 10 — Model benchmarking | Not started |
