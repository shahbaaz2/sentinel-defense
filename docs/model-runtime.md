# Local model runtime (Phase 5)

MLX / MLX-LM, Apple-Silicon-only, loaded **in-process** inside the Sentinel API worker - not a
separate `mlx_lm.server` process. See DECISIONS.md for why in-process won over a sidecar server;
this doc is the practical "what actually runs, how big is it, how fast is it" reference.

## Model

`mlx-community/Qwen3-4B-Instruct-2507-4bit` - Qwen3-4B-Instruct (July 2025 update), MLX 4-bit
quantized community conversion. This is the exact model the Phase 5 blueprint named as the
preferred first choice; no substitution was needed on this machine.

- Source: Hugging Face Hub (`mlx-community/Qwen3-4B-Instruct-2507-4bit`)
- Cached locally under `~/.cache/huggingface/hub/` after first download (~2.1 GB on disk)
- Runtime: `mlx-lm` (`ai/providers/mlx_provider.py`), decoding with `temp=0.0` (greedy, deterministic
  - this is a structured-extraction task over a fixed evidence pack, not creative generation)
- No LoRA fine-tuning, no quantization changes - used exactly as published by mlx-community

## Provenance recorded per assessment

Every row in `ai_assessments` (`domain/models/orm.py`) carries `model_name`, `model_provider`,
`model_revision` (the Hugging Face snapshot hash, read from the local cache path -
`ai/providers/mlx_provider.py::_load_sync`), and `model_quantization` (`"4bit"`, parsed from the
model name). `GET /api/v1/ai/status` and the System Assurance page expose the same runtime/provider
fields live.

## Measured resource usage (this machine: M1-class Apple Silicon, 16GB unified memory, Lite profile)

| Measurement | Value |
|---|---|
| Model download size | ~2.1 GB (cached once, reused across restarts) |
| Cold model load time | ~4-5 s (`mlx_lm.load`, first call only - cached in-process after that) |
| Sentinel API worker RSS before any AI call | ~30-50 MB (same ballpark as MissionNet/Demo Control's idle uvicorn workers) |
| Sentinel API worker physical footprint with model loaded (`vmmap -summary`) | ~2.9 GB steady, ~3.4 GB peak during inference |
| Single incident analysis latency (3-15 events, `max_tokens=1500`) | ~13-25 s |
| Single incident analysis latency (15-event high-volume case) | ~62 s |
| SCN-010 live dashboard analysis (real click, real incident) | 49.9 s (`latency_ms` on the persisted assessment) |

None of this is close to the 16 GB ceiling - roughly 3 GB is committed to the model at peak, leaving
over 12 GB for Postgres, three Next.js dev servers, three FastAPI workers, and the browser. Running
SCN-010 while the model is loaded was verified to cause no memory pressure or slowdown to the
deterministic pipeline (see PROGRESS.md's Phase 5 section for the exact run).

`SENTINEL_LLM_TIMEOUT_SECONDS=90` (`.env.example`) gives real analyses (usually <60s) comfortable
headroom while still failing an actually-stuck request in reasonable time; `SENTINEL_LLM_MAX_TOKENS
=1500` was chosen after an initial `700` truncated the model's own JSON mid-string on anything but
the smallest evidence packs (see DECISIONS.md).

## Starting it

There is no separate server to start. `make api` (or the already-running dev API) loads the model
lazily on the **first** `POST /api/v1/incidents/{id}/ai/analyze` call, once, and keeps it resident
for the life of that worker process (`ai/providers/get_provider` is a process-wide singleton - see
DECISIONS.md for why loading it twice must never happen on a 16GB machine). Restarting the API
process unloads the model; the next analyze call reloads it.

To pre-warm the model without going through the dashboard:

```bash
make ai-status   # shows LOADING until the first analyze call, READY after
```

or trigger one real analysis directly:

```bash
curl -X POST http://127.0.0.1:8080/api/v1/incidents/<real-incident-id>/ai/analyze
```

## Offline behavior

Model *weights* must be downloaded once, with internet access, the first time
(`SENTINEL_AI_ENABLED=true` + `SENTINEL_LLM_PROVIDER=mlx`, then any analyze call triggers the
`huggingface_hub` cache fetch). After that, `mlx_lm.load` reads entirely from the local Hugging
Face cache and no further network access is required - verified manually by setting
`HF_HUB_OFFLINE=1` and re-running an analysis against the already-cached model. `make
offline-check` is referenced in the Makefile/RUNBOOK.md but `scripts/offline-check.sh` does not
exist in this repository (a pre-existing gap from an earlier phase, not introduced in Phase 5 - see
DECISIONS.md); writing that script is out of scope for a Phase 5 AI Analyst task and is flagged
there as a known limitation rather than silently worked around.
