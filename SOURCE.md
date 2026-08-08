# ACCELA source baseline

The current upstream installer ships ACCELA inside `deps.tar.gz`, and that archive now exists primarily to carry `bin/ACCELA.AppImage` plus installer assets. For development, this branch is moving away from that opaque release layout.

## Source baseline

Editable source is synchronized from the May 12, 2026 ACCELA-era source snapshot mirrored by `niwia/ASSella`:

- repository: `https://github.com/niwia/ASSella`
- commit: `9a11c5f65da038fa31f2d18189766405994ea2e5`
- destination: `accela-src/src`

That snapshot was chosen because it was created directly from the 2026-05-12 ACCELA source and predates the later ASSella beta development.

Run:

```bash
./tools/sync-accela-source.sh
python3 ./tools/audit-python-imports.py
```

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

## Next packaging step

Once the imported source has been audited, the `accela` installer can be changed to install the source tree into `~/.local/share/ACCELA`, create a small isolated Python environment, install only the dependencies actually imported by the application, and launch `src/main.py` through a stable wrapper. The existing AppImage path can remain as a temporary fallback until that source install is validated.
