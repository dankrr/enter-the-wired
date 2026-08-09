#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/accela-src/src"
VENV="$ROOT/.venv"
CORE_REQ="$ROOT/accela-src/requirements.detected.txt"
AUDIO_REQ="$ROOT/accela-src/requirements.optional-audio.txt"
MEDIA_REQ="$ROOT/accela-src/requirements.optional-media.txt"
CLI_REQ="$ROOT/accela-src/requirements.optional-cli.txt"
DB_REQ="$ROOT/accela-src/requirements.optional-db.txt"
PROCESS_REQ="$ROOT/accela-src/requirements.optional-process.txt"
WINDOWS_REQ="$ROOT/accela-src/requirements.optional-windows.txt"
EXTRAS="${ACCELA_EXTRAS:-}"
FORCE_PIP_QT="${ACCELA_PIP_QT:-0}"

if [ ! -f "$SRC/main.py" ]; then
    echo "Editable ACCELA source is not present."
    echo "Run: $ROOT/tools/sync-accela-source.sh"
    exit 1
fi

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

system_pyqt_available() {
    python3 -c 'from PyQt6.QtCore import QT_VERSION_STR; from PyQt6.QtWidgets import QApplication' >/dev/null 2>&1
}

venv_pyqt_available() {
    "$VENV/bin/python" -c 'from PyQt6.QtCore import QT_VERSION_STR; from PyQt6.QtWidgets import QApplication' >/dev/null 2>&1
}

if [ ! -x "$VENV/bin/python" ]; then
    if [ "$FORCE_PIP_QT" != "1" ] && system_pyqt_available; then
        echo "System PyQt6 detected; reusing the host Qt installation."
        python3 -m venv --system-site-packages "$VENV"
    else
        python3 -m venv "$VENV"
    fi
fi

"$VENV/bin/python" -m pip install --upgrade pip

mapfile -t imports < <(python3 "$ROOT/tools/audit-python-imports.py")

: > "$CORE_REQ"
printf '%s\n' "just-playback" > "$AUDIO_REQ"
: > "$MEDIA_REQ"
: > "$CLI_REQ"
: > "$DB_REQ"
: > "$PROCESS_REQ"
: > "$WINDOWS_REQ"
rm -f "$ROOT/accela-src/requirements.optional-steam.txt"

for module in "${imports[@]}"; do
    group="core"

    case "$module" in
        PyQt6)
            if [ "$FORCE_PIP_QT" != "1" ] && venv_pyqt_available; then
                continue
            fi
            package="PyQt6"
            ;;
        bs4) package="beautifulsoup4" ;;
        requests) package="requests" ;;
        urllib3)
            # requests already installs urllib3; avoid duplicating it as a direct requirement.
            continue
            ;;
        configobj) package="configobj" ;;
        cryptography) package="cryptography" ;;
        yaml) package="PyYAML" ;;
        gevent) package="gevent" ;;
        Cryptodome) package="pycryptodomex" ;;
        cachetools) package="cachetools" ;;
        google) package="protobuf" ;;
        typing_extensions) package="typing-extensions" ;;
        cffi) package="cffi" ;;
        pygame) package="pygame" ;;
        tinytag) package="tinytag" ;;
        pkg_resources) package="setuptools" ;;

        psutil)
            package="psutil"
            group="process"
            ;;

        zstandard)
            package="zstandard"
            group="db"
            ;;

        urwid)
            package="urwid"
            group="cli"
            ;;

        just_playback)
            # Dynamically imported by audio_manager; seeded above.
            continue
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
            # Product-info manifest IDs power the normal update checker.
            package="steam[client]"
            ;;

        vdf)
            package="vdf"
            group="windows"
            ;;

        windows_curses)
            package="windows-curses"
            group="windows"
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
        cli) printf '%s\n' "$package" >> "$CLI_REQ" ;;
        db) printf '%s\n' "$package" >> "$DB_REQ" ;;
        process) printf '%s\n' "$package" >> "$PROCESS_REQ" ;;
        windows) printf '%s\n' "$package" >> "$WINDOWS_REQ" ;;
    esac
done

for file in "$CORE_REQ" "$AUDIO_REQ" "$MEDIA_REQ" "$CLI_REQ" "$DB_REQ" "$PROCESS_REQ" "$WINDOWS_REQ"; do
    sort -u -o "$file" "$file"
done

echo "Core Python packages:"
sed 's/^/  /' "$CORE_REQ"

if [ -s "$CORE_REQ" ]; then
    "$VENV/bin/python" -m pip install -r "$CORE_REQ"
fi

if ! venv_pyqt_available; then
    echo
    echo "PyQt6 is not available from the host or source environment."
    echo "Installing the bundled pip Qt runtime..."
    "$VENV/bin/python" -m pip install PyQt6
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
install_extra cli "$CLI_REQ"
install_extra db "$DB_REQ"
install_extra process "$PROCESS_REQ"
install_extra windows "$WINDOWS_REQ"

echo
echo "Source environment ready."
if venv_pyqt_available && [ "$FORCE_PIP_QT" != "1" ] && system_pyqt_available; then
    echo "Qt: using system PyQt6 when available"
else
    echo "Qt: using pip PyQt6"
fi
echo "Run: $ROOT/tools/run-accela-source.sh"
echo "Extras: ACCELA_EXTRAS=audio,media,cli,db,process,windows $ROOT/accela"
echo "Force pip Qt: ACCELA_PIP_QT=1 $ROOT/accela"
