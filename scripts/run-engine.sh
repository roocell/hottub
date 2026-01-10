#!/usr/bin/env bash
set -euo pipefail

ENGINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../engine" && pwd)"
VENV_DIR="$ENGINE_DIR/.venv"
PYTHON="$VENV_DIR/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  echo "Venv not found. Run scripts/setup-venv.sh first." >&2
  exit 1
fi

cd "$ENGINE_DIR"
"$PYTHON" -m spa_engine
