#!/usr/bin/env bash
set -euo pipefail

VENV_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../engine" && pwd)/.venv"
REQ_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../engine" && pwd)/requirements.txt"

python3 -m venv "$VENV_PATH"
"$VENV_PATH/bin/python" -m pip install --upgrade pip
"$VENV_PATH/bin/pip" install -r "$REQ_PATH"

LOCAL_GEOCKOLIB_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/geckolib"
if [ -d "$LOCAL_GEOCKOLIB_PATH" ]; then
  "$VENV_PATH/bin/pip" install -e "$LOCAL_GEOCKOLIB_PATH"
fi

echo "Venv ready at $VENV_PATH"
