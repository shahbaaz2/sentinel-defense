#!/usr/bin/env bash
# Deletes generated lab state (DB rows via seed script) while preserving source code, knowledge, and
# rule bundles. Never deletes files outside the project's own database/containers.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ -f .env ]; then
  set -a; source .env; set +a
fi

echo "Resetting MissionNet + Sentinel lab state to seeded baseline..."

if [ ! -x "$REPO_ROOT/.venv/bin/python" ]; then
  echo "No .venv found; run scripts/bootstrap-mac.sh first." >&2
  exit 1
fi

"$REPO_ROOT/.venv/bin/python" -m apps.missionnet.seed --reset

echo "reset-lab complete."
