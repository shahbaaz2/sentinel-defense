# Deploying Sentinel: Vercel + Render + DeepSeek

This is an optional, alternate deployment target - a portfolio/demo-friendly cloud stack, separate
from the local-only, disconnected-capable setup the rest of this repo's docs describe. Nothing
about the local setup changes: a fresh checkout still defaults to Postgres/MissionNet in Colima,
`SENTINEL_LLM_PROVIDER=mock`, and no external network calls. This document is for when you
specifically want a public URL to share.

**Be honest about what changes.** The core "synthetic lab, defensive-only" claim (SECURITY.md)
stays true regardless of where MissionNet runs - it's still fictional data, still no real
classified information. What stops being true once you deploy this way: "disconnected" (Render/
Vercel/DeepSeek all require internet), and "no external AI API" (DeepSeek is a real third-party
API - your evidence packs leave your infrastructure). System Assurance already reflects this
honestly once you set the env vars below (`inference_location`, `internet_required_for_core_demo`)
- don't edit it to claim otherwise.

## What you're deploying

| Component | Where | Notes |
|---|---|---|
| Sentinel dashboard | Vercel | `apps/dashboard` |
| MissionNet Operations Console | Vercel | `apps/missionnet-console` |
| Demo Control Console | Vercel | `apps/demo-control-console` |
| Sentinel API | Render (web service) | `apps/api` |
| MissionNet API | Render (web service) | `apps/missionnet` |
| Demo Control API | Render (web service) | `apps/demo_control` |
| 3x Postgres | Render (managed Postgres) | one database per backend, matching local dev |
| AI Analyst inference | DeepSeek API | replaces local MLX, which needs Apple Silicon Render doesn't have |

**Not deployed / behaves differently in the cloud:**
- **Suricata/Zeek (Phase 8)** run via ephemeral Docker containers (`services/sensor_lab/
  pipeline.py`) - Render's standard web services have no Docker-in-Docker access. Leave
  `SENTINEL_SURICATA_ENABLED`/`SENTINEL_ZEEK_ENABLED` unset (both default `false`) so they report
  `NOT_CONFIGURED`, matching Wazuh/Splunk/Falco. If someone runs SCN-NET-001 on the deployed Demo
  Control anyway, it fails cleanly with a `SensorLabError` in the run's `failure_reason` (`docker`
  not found) - not a crash, just an honest failure. This is expected; no code change is needed to
  "support" it in the cloud.
- **Wazuh/Splunk/Falco** stay `NOT_CONFIGURED` exactly like local dev, unless you have real
  instances to point them at (`docs/integrations.md`, `docs/splunk-integration.md`).

## Before you start: get the accounts and one API key

- A [Render](https://render.com) account (free tier works for a demo; see "Costs" below).
- A [Vercel](https://vercel.com) account, with this repo connected as a GitHub source (Vercel
  needs read access to the repo to deploy from it).
- A [DeepSeek](https://platform.deepseek.com) account and API key, if you want the AI Analyst live
  in the cloud. Skip this and leave `SENTINEL_AI_ENABLED=false` if you just want the deterministic
  detection/response chain public - everything except the AI Analyst panel works identically
  without it.
- Generate one real random secret for lab-control auth (replaces the repo's placeholder
  `dev-only-lab-secret-change-me`):
  ```bash
  openssl rand -hex 32
  ```
  You'll paste this exact same value into three different env vars across two services (see
  below) - it's one shared secret, not three different ones.

**Never paste the DeepSeek API key or the lab secret into a Vercel env var** - Vercel serves the
frontends, which run partly in the visitor's browser; anything set there can end up shipped to
client JavaScript. Both secrets belong only in Render's backend env vars.

## 1. Render: three Postgres databases

Either use `render.yaml` at the repo root (Render dashboard → **New** → **Blueprint** → point at
this repo - it provisions all three databases and all three web services in one pass, though
you'll still fill in the `sync: false` values by hand afterward), or create manually:

1. **New → PostgreSQL** three times: `sentinel-db`, `missionnet-db`, `democontrol-db` (free plan
   is fine for a demo). Note each one's **Internal Connection String** once created.

Render's connection strings use the plain `postgresql://` scheme; `domain/db_url.py::
normalize_async_postgres_url` (used by all three apps' config) upgrades that to
`postgresql+asyncpg://` automatically, so you can paste Render's string in verbatim.

## 2. Render: MissionNet API (deploy and migrate first)

**New → Web Service** → connect this repo.

- **Runtime**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**:
  ```
  alembic -c infrastructure/migrations/missionnet/alembic.ini upgrade head && uvicorn apps.missionnet.main:app --host 0.0.0.0 --port $PORT --app-dir .
  ```
- **Health Check Path**: `/health`
- **Environment variables**:
  | Key | Value |
  |---|---|
  | `MISSIONNET_DATABASE_URL` | `missionnet-db`'s internal connection string |
  | `MISSIONNET_API_HOST` | `0.0.0.0` |
  | `MISSIONNET_LAB_SECRET` | your generated secret |

Deploy it, wait for the health check to go green, and note its public URL (e.g.
`https://sentinel-missionnet.onrender.com`).

## 3. Render: Sentinel API

**New → Web Service**, same repo.

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**:
  ```
  alembic -c infrastructure/migrations/sentinel/alembic.ini upgrade head && uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT --app-dir .
  ```
- **Health Check Path**: `/api/v1/health`
- **Environment variables**:
  | Key | Value |
  |---|---|
  | `SENTINEL_DATABASE_URL` | `sentinel-db`'s internal connection string |
  | `SENTINEL_API_HOST` | `0.0.0.0` |
  | `SENTINEL_ENV` | `production` |
  | `SENTINEL_PLATFORM_LABEL` | `Linux x86_64 (Render)` |
  | `SENTINEL_MISSIONNET_BASE_URL` | MissionNet's Render URL from step 2 |
  | `SENTINEL_MISSIONNET_LAB_SECRET` | your generated secret (same value as `MISSIONNET_LAB_SECRET`) |
  | `SENTINEL_RESPONSE_EXECUTION_ENABLED` | `true` |
  | `SENTINEL_CORS_ALLOWED_ORIGINS` | *(fill in after step 6 - leave as your Render URL for now)* |

  Add these three only if you have a real DeepSeek key ready:
  | `SENTINEL_AI_ENABLED` | `true` |
  | `SENTINEL_LLM_PROVIDER` | `deepseek` |
  | `SENTINEL_LLM_MODEL` | `deepseek-chat` |
  | `SENTINEL_EXTERNAL_AI_ENABLED` | `true` |
  | `SENTINEL_DEEPSEEK_API_KEY` | your real DeepSeek API key |

  Leave `SENTINEL_AI_ENABLED` unset (`false`) if you're skipping DeepSeek for now - the rest of
  Sentinel works identically, exactly like local dev with a fresh checkout.

Deploy it and note its URL (e.g. `https://sentinel-api.onrender.com`).

## 4. Render: Demo Control API

**New → Web Service**, same repo.

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**:
  ```
  alembic -c infrastructure/migrations/demo_control/alembic.ini upgrade head && uvicorn apps.demo_control.main:app --host 0.0.0.0 --port $PORT --app-dir .
  ```
- **Health Check Path**: `/health`
- **Environment variables**:
  | Key | Value |
  |---|---|
  | `DEMOCONTROL_DATABASE_URL` | `democontrol-db`'s internal connection string |
  | `DEMOCONTROL_API_HOST` | `0.0.0.0` |
  | `DEMOCONTROL_MISSIONNET_BASE_URL` | MissionNet's Render URL |
  | `DEMOCONTROL_SENTINEL_BASE_URL` | Sentinel API's Render URL |
  | `DEMOCONTROL_MISSIONNET_LAB_SECRET` | your generated secret |
  | `DEMOCONTROL_CORS_ALLOWED_ORIGINS` | *(fill in after step 6)* |

Optionally go back to Sentinel API's env vars and set `SENTINEL_DEMO_CONTROL_BASE_URL` to this
service's URL now (only affects System Assurance's own reachability check - nothing functional
depends on it).

## 5. Vercel: three frontends

Vercel deploys one **project** per app; since this is a monorepo, set each project's **Root
Directory** to the app's own folder.

For each of the three, **Add New → Project**, import this repo, then:

| Project | Root Directory | Env vars |
|---|---|---|
| Sentinel dashboard | `apps/dashboard` | `SENTINEL_API_BASE_URL` = Sentinel API's Render URL; `NEXT_PUBLIC_SENTINEL_API_BASE_URL` = same value (the dashboard's SSE connection is opened from browser JS, so it needs the public variant too) |
| MissionNet console | `apps/missionnet-console` | `MISSIONNET_API_BASE_URL` = MissionNet's Render URL (server-side only - this console has no client-side fetches) |
| Demo Control console | `apps/demo-control-console` | `DEMOCONTROL_API_BASE_URL` = Demo Control's Render URL; `NEXT_PUBLIC_DEMOCONTROL_API_BASE_URL` = same value |

Vercel auto-detects Next.js - no build command changes needed. Deploy all three and note each
project's URL (e.g. `https://sentinel-dashboard.vercel.app`).

## 6. Lock down CORS

Go back to Render and update:

- **Sentinel API**'s `SENTINEL_CORS_ALLOWED_ORIGINS` → the dashboard's Vercel URL (comma-separate
  multiple origins if you use a custom domain too, e.g.
  `https://sentinel-dashboard.vercel.app,https://sentinel.yourdomain.com`).
- **Demo Control API**'s `DEMOCONTROL_CORS_ALLOWED_ORIGINS` → the Demo Control console's Vercel URL.

MissionNet's API needs no CORS entry - its console has no client-side browser fetches (Next.js
server components only), so there's no cross-origin browser request to allow.

Redeploy both services after changing these (Render redeploys automatically on env var save).

## 7. Verify

```bash
curl https://sentinel-api.onrender.com/api/v1/health
curl https://sentinel-missionnet.onrender.com/health
curl https://sentinel-demo-control.onrender.com/health
curl https://sentinel-api.onrender.com/api/v1/system/assurance | python3 -m json.tool
```

`system/assurance` should show `platform: "Linux x86_64 (Render)"`, and - if you configured
DeepSeek - `inference_location: "cloud (DeepSeek API)"` and `internet_required_for_core_demo:
"YES - the AI Analyst calls the DeepSeek API"`. This is the honest, correct state for this
deployment - it should look different from a local run's System Assurance page, not identical.

Open the dashboard's Vercel URL, confirm Overview/Incidents load, then open the Demo Control
console's Vercel URL and run SCN-001 or SCN-010 - it should PASS exactly like the local demo,
just end to end over the internet.

## Costs and known rough edges

- Render's free web services spin down after 15 minutes of inactivity and take ~30-60s to wake on
  the next request - the first request after idle will be slow. Free Postgres instances expire
  after Render's current free-tier retention window (check Render's own pricing page for the
  current number - this has changed before). Upgrade to a paid plan on any service you want to
  stay warm/permanent.
- DeepSeek API calls cost money per token past any free credits DeepSeek gives new accounts - keep
  `SENTINEL_AI_ENABLED=false` until you're ready to spend on it.
- SCN-NET-001 (Suricata/Zeek) will not pass in this deployment - see "Not deployed" above. This is
  expected, not a bug to chase.

## Rolling back to local-only

Nothing here is one-way. To go back to the fully local setup, just don't set any of these env
vars in your local `.env` - every default (`SENTINEL_LLM_PROVIDER=mock`,
`SENTINEL_CORS_ALLOWED_ORIGINS` pointed at `127.0.0.1:3000`, `SENTINEL_DATABASE_URL` pointed at
Colima's Postgres) is unchanged from before this document existed.
