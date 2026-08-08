#!/usr/bin/env python3
"""List third-party imports used by the editable ACCELA source tree."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "accela-src" / "src"
STDLIB = set(getattr(sys, "stdlib_module_names", ()))


def top_level(name: str) -> str:
    return name.split(".", 1)[0]


def imports_from(path: Path) -> set[str]:
    found: set[str] = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:
        print(f"warning: cannot parse {path.relative_to(ROOT)}: {exc}", file=sys.stderr)
        return found

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(top_level(alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(top_level(node.module))
    return found


def main() -> int:
    if not SRC.is_dir():
        print("accela-src/src is missing; run tools/sync-accela-source.sh first", file=sys.stderr)
        return 1

    local_modules = {p.stem for p in SRC.rglob("*.py")}
    local_modules.update(p.name for p in SRC.iterdir() if p.is_dir())

    imported: set[str] = set()
    for path in SRC.rglob("*.py"):
        imported.update(imports_from(path))

    third_party = sorted(
        name for name in imported
        if name not in STDLIB and name not in local_modules and name != "__future__"
    )

    print("\n".join(third_party))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
