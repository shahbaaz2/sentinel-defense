#!/usr/bin/env bash
# Idempotent Mac bootstrap: inspect the machine, install missing prerequisites via Homebrew,
# never clobber tooling that's already installed. Safe to re-run.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "== Machine profile =="
ARCH="$(uname -m)"
echo "arch: $ARCH"
sw_vers
MEM_BYTES="$(sysctl -n hw.memsize)"
MEM_GB=$(( MEM_BYTES / 1073741824 ))
NCPU="$(sysctl -n hw.ncpu)"
echo "memory: ${MEM_GB} GB"
echo "cpus: ${NCPU}"
df -h ~ | tail -n 1

if [ "$ARCH" != "arm64" ]; then
  echo "WARNING: expected arm64 Apple Silicon; got $ARCH. MLX-LM requires Apple Silicon." >&2
fi

if [ "$MEM_GB" -ge 32 ]; then
  PROFILE=full
else
  PROFILE=lite
fi
echo "selected profile: $PROFILE (override with SENTINEL_PROFILE in .env)"

echo
echo "== Developer prerequisites =="
if ! xcode-select -p >/dev/null 2>&1; then
  echo "Apple command line tools missing. Run this yourself, then re-run this script:"
  echo "  xcode-select --install"
  exit 1
fi
echo "xcode-select: OK"

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew missing. Install it yourself from https://brew.sh, then re-run this script." >&2
  exit 1
fi
echo "brew: OK ($(brew --version | head -n1))"

need_brew() {
  local formula="$1"
  if brew list --formula "$formula" >/dev/null 2>&1; then
    echo "  $formula: already installed"
  else
    echo "  $formula: installing..."
    brew install "$formula"
  fi
}

echo "checking/installing: git python@3.12 node pnpm colima docker docker-compose uv jq"
for f in git python@3.12 node pnpm colima docker docker-compose uv jq; do
  need_brew "$f"
done

echo
echo "== Python 3.12 virtualenv =="
PY312="$(brew --prefix python@3.12)/bin/python3.12"
if [ ! -x "$REPO_ROOT/.venv/bin/python" ]; then
  "$PY312" -m venv "$REPO_ROOT/.venv" 2>/dev/null || uv venv "$REPO_ROOT/.venv" --python "$PY312"
  echo "created .venv"
else
  echo ".venv already exists"
fi

if [ -f "$REPO_ROOT/requirements-dev.txt" ]; then
  # shellcheck disable=SC1091
  source "$REPO_ROOT/.venv/bin/activate"
  uv pip install -r "$REPO_ROOT/requirements-dev.txt"
  deactivate
fi

echo
echo "== Node dependencies =="
if [ -f "$REPO_ROOT/apps/dashboard/package.json" ]; then
  (cd "$REPO_ROOT/apps/dashboard" && pnpm install)
fi
if [ -f "$REPO_ROOT/apps/missionnet/package.json" ]; then
  (cd "$REPO_ROOT/apps/missionnet" && pnpm install)
fi

echo
echo "== .env =="
if [ ! -f "$REPO_ROOT/.env" ]; then
  cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
  echo "created .env from .env.example (development placeholders only)"
else
  echo ".env already exists, leaving it alone"
fi

echo
echo "Bootstrap complete. Profile: $PROFILE. Next: make dev-up"
