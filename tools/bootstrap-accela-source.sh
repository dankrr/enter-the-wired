#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/accela-src/src"
VENV="$ROOT/.venv"
CORE_REQ="$ROOT/accela-src/requirements.detected.txt"
AUDIO_REQ="$ROOT/accela-src/requirements.optional-audio.txt"
MEDIA_REQ="$ROOT/accela-src/requirements.optional-media.txt"
STEAM_REQ="$ROOT/accela-src/requirements.optional-steam.txt"
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

: > "$CORE_REQ"
: > "$AUDIO_REQ"
: > "$MEDIA_REQ"
: > "$STEAM_REQ"

for module in "${imports[@]}"; do
    group="core"

    case "$module" in
        PyQt6) package="PyQt6" ;;
        psutil) package="psutil" ;;
        bs4) package="beautifulsoup4" ;;
        requests) package="requests" ;;
        urllib3) package="urllib3" ;;
        configobj) package="configobj" ;;
        cryptography) package="cryptography" ;;
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
        pkg_resources) package="setuptools" ;;

        just_playback)
            package="just-playback"
            group="audio"
            ;;

        PIL)
            package="Pillow"
            group="media"
            ;;
        numpy)
            package="numpy"
            group="media"
            ;;

        steam)
            package="steam[client]"
            group="steam"
            ;;

        windows_curses)
            # Windows-only compatibility import. This branch targets Linux.
            continue
            ;;

        *)
            echo "Unmapped third-party import: $module" >&2
            continue
            ;;
    esac

    case "$group" in
        core) printf '%s\n' "$package" >> "$CORE_REQ" ;;
        audio) printf '%s\n' "$package" >> "$AUDIO_REQ" ;;
        media) printf '%s\n' "$package" >> "$MEDIA_REQ" ;;
        steam) printf '%s\n' "$package" >> "$STEAM_REQ" ;;
    esac
done

for file in "$CORE_REQ" "$AUDIO_REQ" "$MEDIA_REQ" "$STEAM_REQ"; do
    sort -u -o "$file" "$file"
done

echo "Core Python packages:"
sed 's/^/  /' "$CORE_REQ"

if [ -s "$CORE_REQ" ]; then
    "$VENV/bin/python" -m pip install -r "$CORE_REQ"
fi

install_extra() {
    local name="$1"
    local req="$2"

    [ -s "$req" ] || return 0

    echo
    echo "Optional $name packages:"
    sed 's/^/  /' "$req"

    case ",$EXTRAS," in
        *,"$name",*|*,all,*)
            echo "Installing optional $name support..."
            "$VENV/bin/python" -m pip install -r "$req"
            ;;
        *)
            echo "Skipping optional $name support."
            ;;
    esac
}

install_extra audio "$AUDIO_REQ"
install_extra media "$MEDIA_REQ"
install_extra steam "$STEAM_REQ"

echo
echo "Source environment ready."
echo "Run: $ROOT/tools/run-accela-source.sh"
echo "Extras: ACCELA_EXTRAS=audio,media,steam $ROOT/accela"
