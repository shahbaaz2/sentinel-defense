#!/usr/bin/env bash
# Aggregate health check. Exits non-zero on any critical failure so CI/Claude can trust the result.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
if [ -f .env ]; then
  set -a; source .env; set +a
fi

API_HOST="${SENTINEL_API_HOST:-127.0.0.1}"
API_PORT="${SENTINEL_API_PORT:-8080}"
MISSIONNET_HOST="${MISSIONNET_API_HOST:-127.0.0.1}"
MISSIONNET_PORT="${MISSIONNET_API_PORT:-8090}"
DEMOCONTROL_HOST="${DEMOCONTROL_API_HOST:-127.0.0.1}"
DEMOCONTROL_PORT="${DEMOCONTROL_API_PORT:-8100}"

FAIL=0

check() {
  local name="$1"; local cmd="$2"; local critical="${3:-1}"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "PASS  $name"
  else
    if [ "$critical" = "1" ]; then
      echo "FAIL  $name (critical)"
      FAIL=1
    else
      echo "WARN  $name (non-critical, not yet enabled)"
    fi
  fi
}

echo "== Sentinel health check =="
check "PostgreSQL reachable" "docker exec sentinel-postgres pg_isready -U sentinel" 1
check "Sentinel API /health" "curl -fsS http://${API_HOST}:${API_PORT}/api/v1/health" 1
check "Sentinel dashboard reachable" "curl -fsS http://127.0.0.1:3000" 0
check "MissionNet health" "curl -fsS http://${MISSIONNET_HOST}:${MISSIONNET_PORT}/health" 1
check "MissionNet dashboard reachable" "curl -fsS http://127.0.0.1:3100" 0
check "MissionNet DB migration applied" "docker exec sentinel-postgres psql -U missionnet -d missionnet -tAc \"select 1 from alembic_version\"" 1
check "Sentinel DB migration applied" "docker exec sentinel-postgres psql -U sentinel -d sentinel -tAc \"select 1 from alembic_version\"" 1
check "Demo Control API health" "curl -fsS http://${DEMOCONTROL_HOST}:${DEMOCONTROL_PORT}/health" 1
check "Demo Control console reachable" "curl -fsS http://127.0.0.1:3200" 0
check "Demo Control DB migration applied" "docker exec sentinel-postgres psql -U democontrol -d democontrol -tAc \"select 1 from alembic_version\"" 1
check "Local model endpoint" "curl -fsS ${SENTINEL_LLM_BASE_URL:-http://127.0.0.1:8000/v1}/models" 0
check "Knowledge bundle present" "[ -n \"${SENTINEL_KNOWLEDGE_BUNDLE:-}\" ]" 0
check "Policy bundle present" "[ -n \"${SENTINEL_POLICY_BUNDLE:-}\" ]" 0

echo
if [ "$FAIL" -ne 0 ]; then
  echo "Result: one or more CRITICAL checks failed."
  exit 1
fi
echo "Result: no critical failures (some services may be intentionally not-yet-enabled for this phase)."
exit 0
