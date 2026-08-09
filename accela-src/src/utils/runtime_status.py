import importlib.util
import sys
from pathlib import Path
from typing import Dict

from utils.helpers import get_dotnet_path
from utils.paths import Paths


def _module_available(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _linux_process_running(name: str) -> bool:
    proc = Path("/proc")
    if not proc.exists():
        return False

    try:
        entries = proc.iterdir()
    except OSError:
        return False

    for entry in entries:
        if not entry.name.isdigit():
            continue
        try:
            if (entry / "comm").read_text(errors="ignore").strip().lower() == name.lower():
                return True
        except OSError:
            continue
    return False


def _steam_running() -> bool:
    if sys.platform == "linux":
        return _linux_process_running("steam")

    try:
        import psutil
    except ImportError:
        return False

    wanted = "steam.exe" if sys.platform == "win32" else "steam"
    try:
        return any(
            (proc.info.get("name") or "").lower() == wanted
            for proc in psutil.process_iter(["name"])
        )
    except psutil.Error:
        return False


def _slssteam_ready() -> bool:
    if sys.platform != "linux":
        return False

    roots = [
        Path("/usr/lib32"),
        Path.home() / ".local/share/SLSsteam",
        Path.home() / ".var/app/com.valvesoftware.Steam/.local/share/SLSsteam",
    ]
    library_names = ("library-inject.so", "libSLS-library-inject.so")
    sls_names = ("SLSsteam.so", "libSLSsteam.so")

    for root in roots:
        has_sls = any((root / name).exists() for name in sls_names)
        has_inject = any((root / name).exists() for name in library_names)
        if has_sls and has_inject:
            return True
    return False


def _slscheevo_ready() -> bool:
    executable = "SLScheevo.exe" if sys.platform == "win32" else "SLScheevo"
    root = Paths.deps("SLScheevo")
    return (root / executable).exists() or (root / "SLScheevo.py").exists()


def _directory_has_files(path: Path) -> bool:
    try:
        return path.exists() and path.is_dir() and next(path.iterdir(), None) is not None
    except OSError:
        return False


def _steamless_ready() -> bool:
    return _directory_has_files(Paths.deps("Steamless"))


def _steamless_aio_ready() -> bool:
    return _directory_has_files(Paths.deps("Steamless-AIO"))


def get_runtime_status() -> Dict[str, dict]:
    """Return lightweight local health checks for core and optional runtime pieces."""
    dotnet = get_dotnet_path()
    depot_downloader = Paths.deps("DepotDownloader.dll").exists()
    steam_running = _steam_running()
    slssteam = _slssteam_ready()
    steam_api = _module_available("steam.client")
    slscheevo = _slscheevo_ready()
    steamless = _steamless_ready()
    steamless_aio = _steamless_aio_ready()

    return {
        "steam": {
            "label": "Steam",
            "ready": steam_running,
            "status": "Running" if steam_running else "Not running",
            "required": False,
        },
        "slssteam": {
            "label": "SLSsteam",
            "ready": slssteam,
            "status": "Ready" if slssteam else "Missing",
            "required": sys.platform == "linux",
        },
        "depot_downloader": {
            "label": "DepotDownloader",
            "ready": depot_downloader and dotnet is not None,
            "status": "Ready" if depot_downloader and dotnet is not None else "Missing runtime",
            "required": True,
        },
        "steam_api": {
            "label": "Steam update API",
            "ready": steam_api,
            "status": "Ready" if steam_api else "Missing",
            "required": True,
        },
        "dotnet": {
            "label": ".NET 9",
            "ready": dotnet is not None,
            "status": "Ready" if dotnet is not None else "Missing",
            "required": True,
        },
        "slscheevo": {
            "label": "Achievements",
            "ready": slscheevo,
            "status": "Ready" if slscheevo else "SLScheevo missing",
            "required": False,
        },
        "steamless": {
            "label": "Steamless",
            "ready": steamless,
            "status": "Ready" if steamless else "Missing",
            "required": False,
        },
        "steamless_aio": {
            "label": "Steamless-AIO",
            "ready": steamless_aio,
            "status": "Ready" if steamless_aio else "Missing",
            "required": False,
        },
    }
