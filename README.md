# Sentinel

> **SYNTHETIC LAB — DEFENSIVE ONLY.** Everything in this repository is local, synthetic, and
> disconnected from real systems. It contains no real classified information, CUI, production
> credentials, or real operational targets. It is not DoD-certified, CMMC-certified, accredited, or
> suitable for production use solely by existing. See [SECURITY.md](SECURITY.md).

Sentinel is a locally deployable, disconnected-capable cyber-defense command platform prototype. It
ingests synthetic telemetry and real security-tool output (Suricata, Zeek, and - contract-tested -
Wazuh and Splunk) through one vendor-neutral adapter boundary, detects suspicious activity with
deterministic rules, uses a local LLM to correlate evidence and recommend an approved response, and
executes only policy-authorized, auditable containment with verification and rollback. The LLM never
has arbitrary shell/SQL/SSH/firewall access — it returns schema-validated analysis and picks from a
pre-approved playbook list. Sentinel is SIEM-agnostic: it adds normalization, evidence-grounded local
AI, human-approved response, verification, and provenance on top of tools an organization already
runs - it does not replace Splunk or any existing SIEM.

This is **three connected deliverables** (see [DECISIONS.md](DECISIONS.md) for the full rationale):

1. **Sentinel** — the defensive platform itself.
2. **MissionNet** — the independently runnable synthetic mission-information app that Sentinel protects.
3. **Demo Control** — a safe scenario harness that changes MissionNet and observes Sentinel's independent
   reaction; it never fakes a detection or response.

## Architecture

```
DETECTION PLANE                     AI PLANE                         RESPONSE PLANE
Sensors + rules                     Evidence + RAG                   Policy + execution
-------------------------------     ---------------------------      ------------------------------
MissionNet audit events             Evidence pack                    Playbook registry
Synthetic/fixture sensors           Local MLX model (Qwen3-4B)       Authorization checks
Deterministic detection rules       ATT&CK / KEV / runbooks          Human approval
              \                           |                              /
               \__________________________|_____________________________/
                                          |
                                  INCIDENT + AUDIT RECORD
```

## Machine profile

Detected and pinned in `DECISIONS.md`: **Lite** (16 GB RAM, Apple Silicon, macOS). Native MLX inference
+ FastAPI + Next.js run on the host; PostgreSQL + MissionNet containers run in Colima.

## Quickstart

```bash
make bootstrap   # check/install prerequisites (idempotent, does not clobber existing tooling)
make dev-up      # start Colima, Postgres, MissionNet
make api         # run FastAPI on :8080
make dashboard   # run Sentinel dashboard on :3000 (separate terminal)
make health      # verify everything is reachable
make test        # run Python + TypeScript tests
```

Then open:
- Sentinel dashboard: http://127.0.0.1:3000
- MissionNet Operations Console: http://127.0.0.1:3100
- Demo Control (scenario orchestration): http://127.0.0.1:3200 (`make demo-control`, `make demo-control-console`)
- Sentinel API docs: http://127.0.0.1:8080/docs

For the full live demo (drive MissionNet, watch Sentinel detect it independently, verify PASS), see
[docs/demo-runbook.md](docs/demo-runbook.md) — or manually: run `make ingest-once` after causing a
real MissionNet signal, see
[RUNBOOK.md](RUNBOOK.md#create-a-phase-2-test-event-and-verify-detectionincident).

## Feature matrix (updated as phases land)

| Capability | Status |
|---|---|
| Repo scaffold, health endpoint, shells | **Phase 0 — done and verified** |
| MissionNet real synthetic app | **Phase 1 — done and verified** |
| Normalized events, deterministic detection, incidents | **Phase 2 — done and verified** |
| Demo Control / SCN-010 scenario | **Phase 3 — done and verified** |
| Sentinel dashboard (posture, incidents, investigation, live SSE) | **Phase 4 — done and verified** |
| Local MLX AI analyst (evidence-grounded, read-only) | **Phase 5 — done and verified** |
| Playbooks, deterministic policy engine, human approval | **Phase 6 — done and verified** |
| Deterministic response execution, verification, rollback | **Phase 7 — done and verified** |
| Real sensor adapters (Suricata/Zeek live; Wazuh/Splunk/Falco contract-tested) | **Phase 8 — done and verified** |
| Validation, coverage, offline hardening | Phase 9 — not started |
| Model benchmarking | Phase 10 — not started |

See [PROGRESS.md](PROGRESS.md) for exactly what currently works and what was actually tested.

## Documents

- [PROGRESS.md](PROGRESS.md) — current phase, what passes, next task.
- [DECISIONS.md](DECISIONS.md) — ADR-style decisions with rationale.
- [RUNBOOK.md](RUNBOOK.md) — start/stop/reset/troubleshooting/offline instructions.
- [SECURITY.md](SECURITY.md) — synthetic-only scope and prohibited uses.
- [docs/data-contracts.md](docs/data-contracts.md) — current schema definitions (MissionNet + Sentinel).
- [docs/detection-engine.md](docs/detection-engine.md) — how the 6 deterministic lab rules work.
- [docs/incident-correlation.md](docs/incident-correlation.md) — how detections become incidents.
- [docs/scenario-controller.md](docs/scenario-controller.md) — Demo Control architecture and scenario format.
- [docs/demo-runbook.md](docs/demo-runbook.md) — live demo walkthrough, including SCN-010 and SCN-NET-001.
- [docs/ai-analyst.md](docs/ai-analyst.md), [docs/model-runtime.md](docs/model-runtime.md) — the local AI Analyst.
- [docs/response-playbooks.md](docs/response-playbooks.md), [docs/policy-engine.md](docs/policy-engine.md), [docs/human-approval.md](docs/human-approval.md) — playbooks, policy, and approval (Phase 6).
- [docs/response-executor.md](docs/response-executor.md), [docs/verification-and-rollback.md](docs/verification-and-rollback.md) — bounded execution (Phase 7).
- [docs/integrations.md](docs/integrations.md) — the vendor-neutral adapter registry and every Phase 8 sensor.
- [docs/splunk-integration.md](docs/splunk-integration.md) — Splunk as a read-only, first-class enterprise integration target.
- [docs/sensor-pipeline.md](docs/sensor-pipeline.md) — the real Suricata/Zeek pipeline behind SCN-NET-001.
