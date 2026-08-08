#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/accela-src/src"
VENV="$ROOT/.venv"
REQ="$ROOT/accela-src/requirements.detected.txt"
OPTIONAL_REQ="$ROOT/accela-src/requirements.optional.txt"
EXTRAS="${ACCELA_EXTRAS:-}"

if [ ! -f "$SRC/main.py" ]; then
    echo "Editable ACCELA source is not present."
    echo "Run: $ROOT/tools/sync-accela-source.sh"
    exit 1
fi

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

if [ ! -x "$VENV/bin/python" ]; then
    python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade pip

mapfile -t imports < <(python3 "$ROOT/tools/audit-python-imports.py")

: > "$REQ"
: > "$OPTIONAL_REQ"
for module in "${imports[@]}"; do
    optional=0
    case "$module" in
        PyQt6) package="PyQt6" ;;
        psutil) package="psutil" ;;
        bs4) package="beautifulsoup4" ;;
        requests) package="requests" ;;
        configobj) package="configobj" ;;
        cryptography) package="cryptography" ;;
        PIL) package="Pillow" ;;
        numpy) package="numpy" ;;
        zstandard) package="zstandard" ;;
        yaml) package="PyYAML" ;;
        gevent) package="gevent" ;;
        vdf) package="vdf" ;;
        urwid) package="urwid" ;;
        Cryptodome) package="pycryptodomex" ;;
        cachetools) package="cachetools" ;;
        google) package="protobuf" ;;
        typing_extensions) package="typing-extensions" ;;
        cffi) package="cffi" ;;
        pygame) package="pygame" ;;
        tinytag) package="tinytag" ;;
        just_playback)
            package="just-playback"
            optional=1
            ;;
        pkg_resources) package="setuptools" ;;
        *)
            echo "Unmapped third-party import: $module" >&2
            continue
            ;;
    esac

    if [ "$optional" -eq 1 ]; then
        printf '%s\n' "$package" >> "$OPTIONAL_REQ"
    else
        printf '%s\n' "$package" >> "$REQ"
    fi
done

sort -u -o "$REQ" "$REQ"
sort -u -o "$OPTIONAL_REQ" "$OPTIONAL_REQ"

echo "Core Python packages:"
sed 's/^/  /' "$REQ"

if [ -s "$REQ" ]; then
    "$VENV/bin/python" -m pip install -r "$REQ"
fi

if [ -s "$OPTIONAL_REQ" ]; then
    echo
    echo "Optional Python packages:"
    sed 's/^/  /' "$OPTIONAL_REQ"

    case ",$EXTRAS," in
        *,audio,*|*,all,*)
            echo "Installing optional audio support..."
            "$VENV/bin/python" -m pip install -r "$OPTIONAL_REQ"
            ;;
        *)
            echo "Skipping optional audio support."
            echo "Re-run with ACCELA_EXTRAS=audio to install it."
            ;;
    esac
fi

echo
echo "Source environment ready."
echo "Run: $ROOT/tools/run-accela-source.sh"
