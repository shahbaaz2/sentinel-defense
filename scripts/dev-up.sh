#!/usr/bin/env bash
# Starts Colima (if not running) and the Lite compose profile: Postgres + MissionNet.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v colima >/dev/null 2>&1; then
  echo "colima not found. Run scripts/bootstrap-mac.sh first." >&2
  exit 1
fi

if ! colima status >/dev/null 2>&1; then
  echo "Starting Colima (Lite profile: 4 CPU / 6 GB RAM / 60 GB disk)..."
  colima start --cpu 4 --memory 6 --disk 60
else
  echo "Colima already running."
fi

echo "Docker context:"
docker context show

echo "Starting Postgres (docker compose)..."
docker-compose -f "$REPO_ROOT/infrastructure/compose/docker-compose.yml" up -d

echo "dev-up complete. Postgres is in Colima; FastAPI/Next.js run natively on the host."
echo "Next: make api (separate terminal), make missionnet (separate terminal), make dashboard, then make health."
