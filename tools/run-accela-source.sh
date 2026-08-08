#!/usr/bin/env bash
set -euo pipefail

# Resolve the real script location even when launched through
# ~/.local/bin/accela-dev -> tools/run-accela-source.sh.
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd)"
SRC="$ROOT/accela-src/src"
PYTHON="$ROOT/.venv/bin/python"

if [ ! -f "$SRC/main.py" ]; then
    echo "Editable ACCELA source is missing." >&2
    echo "Expected: $SRC/main.py" >&2
    echo "Repo root resolved as: $ROOT" >&2
    exit 1
fi

if [ ! -x "$PYTHON" ]; then
    echo "Source environment is missing." >&2
    echo "Run: $ROOT/tools/bootstrap-accela-source.sh" >&2
    exit 1
fi

cd "$SRC"
exec "$PYTHON" main.py "$@"
