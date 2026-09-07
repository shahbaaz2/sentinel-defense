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
"$REPO_ROOT/.venv/bin/python" -m services.event_ingestor.reset
# ^ also clears Suricata/Zeek's generated eve.json/log output (services/event_ingestor/reset.py) -
# every reset path (this script, `make sentinel-reset`, and every Demo Control scenario's own
# automatic lab_reset via POST /api/v1/admin/reset) goes through that one function, so the fix
# lives there, not duplicated here. Its intermediate pcap is regenerated fresh on every
# network-sensor run regardless, so it's not part of what "reset" needs to guarantee.
rm -rf "$REPO_ROOT/var/sensor-lab/pcap"

echo "reset-lab complete."
