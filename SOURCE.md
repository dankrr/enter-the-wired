# ACCELA source baseline

The current upstream installer ships ACCELA inside `deps.tar.gz`, and that archive now exists primarily to carry `bin/ACCELA.AppImage` plus installer assets. The `dev` branch is moving away from that opaque release layout.

## Source baseline

Editable source is synchronized from the May 12, 2026 ACCELA-era source snapshot mirrored by `niwia/ASSella`:

- repository: `https://github.com/niwia/ASSella`
- commit: `9a11c5f65da038fa31f2d18189766405994ea2e5`
- destination: `accela-src/src`

That snapshot was chosen because it was created directly from the 2026-05-12 ACCELA source and predates the later ASSella beta development.

Materialize it once in a checkout:

```bash
./tools/sync-accela-source.sh
```

Then inspect exactly which third-party Python modules the source imports:

```bash
python3 ./tools/audit-python-imports.py
```

## Lean source mode

`./accela` now prefers editable source mode whenever `accela-src/src/main.py` exists. In source mode it does not download `deps.tar.gz` or the AppImage.

The bootstrap creates a repository-local `.venv`, converts detected import names to pip package names, installs only those detected packages, and creates a launcher at `~/.local/bin/accela-dev`.

You can also run the pieces directly:

```bash
./tools/bootstrap-accela-source.sh
./tools/run-accela-source.sh
```

Changes made under `accela-src/src` are used immediately by the source launcher.

## What we intentionally do not vendor

The source sync excludes packaged/runtime payloads rather than checking large opaque artifacts into Git:

- ACCELA AppImage
- `deps.tar.gz`
- SLSsteam binaries
- bundled workshop downloader binaries
- bundled Steamless shell/package payloads
- `src/deps`
- Python virtual environments and build output

The goal is to keep the repository centered on editable application code and make dependencies explicit rather than burying them inside an AppImage.

## Legacy fallback

Until `accela-src` is committed to the branch, a curl-only install has no source tree available and `accela` falls back to the existing AppImage package. Set `ACCELA_FORCE_APPIMAGE=1` to deliberately test that path from a source checkout.

Once the source tree is committed, we can remove that fallback after validating the source build on desktop Linux and Steam Deck/Game Mode.
