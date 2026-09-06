#!/usr/bin/env bash
# Stops project containers. Leaves Colima itself running (use `colima stop` for that).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if colima status >/dev/null 2>&1; then
  docker-compose -f "$REPO_ROOT/infrastructure/compose/docker-compose.yml" down
else
  echo "Colima is not running; nothing to stop."
fi
