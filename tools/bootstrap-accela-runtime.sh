#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/accela-src/src/deps"
CACHE="$ROOT/.vendor/assella-runtime"
SOURCE_REPO="https://github.com/niwia/ASSella.git"
SOURCE_COMMIT="9a11c5f65da038fa31f2d18189766405994ea2e5"

RUNTIME_FILES=(
    DepotDownloader.dll
    DepotDownloader.deps.json
    DepotDownloader.runtimeconfig.json
    SteamKit2.dll
    protobuf-net.dll
    protobuf-net.Core.dll
    QRCoder.dll
    System.IO.Hashing.dll
    ZstdSharp.dll
)

all_present=true
for file in "${RUNTIME_FILES[@]}"; do
    if [ ! -f "$DEST/$file" ]; then
        all_present=false
        break
    fi
done

if [ "$all_present" = true ]; then
    echo "Downloader runtime already present."
    exit 0
fi

command -v git >/dev/null || {
    echo "git is required to fetch the ACCELA downloader runtime." >&2
    exit 1
}

rm -rf "$CACHE"
mkdir -p "$(dirname "$CACHE")" "$DEST"

echo "Fetching minimal DepotDownloader runtime..."
git clone --quiet --filter=blob:none --no-checkout "$SOURCE_REPO" "$CACHE"
git -C "$CACHE" sparse-checkout init --no-cone

{
    for file in "${RUNTIME_FILES[@]}"; do
        printf '/src/deps/%s\n' "$file"
    done
} > "$CACHE/.git/info/sparse-checkout"

git -C "$CACHE" checkout --quiet "$SOURCE_COMMIT"

for file in "${RUNTIME_FILES[@]}"; do
    source_file="$CACHE/src/deps/$file"
    if [ ! -f "$source_file" ]; then
        echo "Missing runtime file in pinned source: $file" >&2
        rm -rf "$CACHE"
        exit 1
    fi
    install -Dm644 "$source_file" "$DEST/$file"
done

rm -rf "$CACHE"
echo "Downloader runtime ready: $DEST"
