#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/accela-src/src"
PYTHON="$ROOT/.venv/bin/python"

if [ ! -f "$SRC/main.py" ]; then
    echo "Editable ACCELA source is missing." >&2
    echo "Run: $ROOT/tools/sync-accela-source.sh" >&2
    exit 1
fi

if [ ! -x "$PYTHON" ]; then
    echo "Source environment is missing." >&2
    echo "Run: $ROOT/tools/bootstrap-accela-source.sh" >&2
    exit 1
fi

cd "$SRC"
exec "$PYTHON" main.py "$@"
