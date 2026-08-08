#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="$ROOT/.vendor/assella"
DEST="$ROOT/accela-src"
SOURCE_REPO="https://github.com/niwia/ASSella.git"
# First ASSella snapshot based on the 2026-05-12 ACCELA source.
# We use it as a practical source mirror and deliberately do not vendor its
# bundled AppImage/SLSsteam/workshop/Steamless payloads.
SOURCE_COMMIT="9a11c5f65da038fa31f2d18189766405994ea2e5"

command -v git >/dev/null || { echo "git is required" >&2; exit 1; }

rm -rf "$CACHE"
mkdir -p "$(dirname "$CACHE")" "$DEST"

git clone --quiet --filter=blob:none --no-checkout "$SOURCE_REPO" "$CACHE"
git -C "$CACHE" sparse-checkout init --cone
git -C "$CACHE" sparse-checkout set src
git -C "$CACHE" checkout --quiet "$SOURCE_COMMIT"

rm -rf "$DEST/src"
mkdir -p "$DEST/src"
cp -a "$CACHE/src/." "$DEST/src/"

# Keep the editable application source/resources; drop bundled runtime payloads
# and generated Python files so the working tree stays lean.
rm -rf "$DEST/src/deps"
find "$DEST/src" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$DEST/src" -type f -name '*.pyc' -delete 2>/dev/null || true

cat > "$DEST/UPSTREAM_SOURCE" <<EOF
repository=$SOURCE_REPO
commit=$SOURCE_COMMIT
imported_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EOF

printf 'Imported editable ACCELA source into %s\n' "$DEST/src"
printf 'Skipped bundled binary/runtime payloads and src/deps.\n'
