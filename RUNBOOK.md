# RUNBOOK

## Start

```bash
make bootstrap    # first time only, or after switching machines
make dev-up       # starts Colima, PostgreSQL, MissionNet
make api          # foreground: FastAPI on :8080
make dashboard    # foreground, separate terminal: Sentinel dashboard on :3000
```

MissionNet's own dashboard runs on :3100 once Phase 1 lands (`make missionnet`).

## Stop

```bash
make dev-down     # stops containers, leaves Colima running
colima stop       # stops the Colima VM entirely
```

## Reset the lab

```bash
make reset-lab
```

Restores MissionNet to its seeded baseline, clears incidents/executions/scenario runs, and preserves
knowledge/rule/policy bundles and the cached model. Never hand-edit the database to "reset" it — always
go through migrations + the seed script so the state is reproducible.

## Health check

```bash
make health
```

Runs `scripts/healthcheck.sh`, which checks PostgreSQL connectivity, API `/health`, dashboard HTTP
response, MissionNet health, the local model endpoint (once Phase 5 is enabled), migration version, and
that a knowledge/policy bundle is present. Exits non-zero on any critical failure.

## Offline check

```bash
make offline-check
```

Disables external AI base URLs, confirms the local model endpoint responds, confirms Postgres/containers
are local, confirms knowledge/rules are present, and runs one scenario end to end with no external
network dependency required.

## Troubleshooting

### Colima will not start
```bash
colima status
```
Check available disk/memory (`df -h ~`). Reduce the allocation in `scripts/dev-up.sh` for this machine's
Lite profile if needed, then `colima stop && colima start`. Do not delete the Colima VM while debugging —
capture logs first (`colima ssh -- dmesg` or `~/.colima/_lima/colima/*.log`).

### Docker CLI cannot reach Colima
Confirm Colima is running and the active Docker context is `colima` (`docker context ls`). Colima
normally activates its own context automatically on `colima start`.

### MLX model is slow or runs out of memory
Confirm the 4-bit quantized model is selected (`SENTINEL_LLM_MODEL` in `.env`). Shorten the evidence pack
or reduce max tokens before reaching for a larger model. Stop any heavy sensor profile that's running
concurrently. Do not swap to an 8B model on this 16 GB machine merely for cybersecurity specialization —
benchmark it first (Phase 10).

### Wazuh (or any Phase 8 sensor) consumes too much memory
Stop that sensor's optional Compose profile. The system must remain functional with sensors marked
`unavailable` — detection and incident handling continue on synthetic/fixture adapters alone.

### Database schema drift
Never hand-edit tables. Use Alembic migrations only (`infrastructure/migrations`). For a broken dev DB,
`make reset-lab` recreates the seeded state from scratch.

### Demo won't reset cleanly
`make reset-lab` should fully restore MissionNet's seed state and clear scenario/incident/execution
records for the next run. If it doesn't, that's a bug — fix the reset path rather than manually patching
the database before a demo.
