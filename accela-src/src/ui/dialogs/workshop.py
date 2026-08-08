import os
import re
import subprocess
import time
import requests
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTextEdit, QCheckBox, QSpinBox, QGroupBox, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from utils.settings import get_settings
from utils.paths import Paths
from utils.helpers import get_base_path
from core import steam_helpers
from core.morrenus_api import BASE_URL
from ui.dialogs.steamlibrary import SteamLibraryDialog

API_WORKSHOP = f"{BASE_URL}/generate/workshopmanifest/{{wid}}"

def extract_workshop_id(raw: str):
    raw = raw.strip()
    m = re.search(r"[?&]id=(\d+)", raw)
    if m: return m.group(1)
    if re.fullmatch(r"\d+", raw): return raw
    return None

def parse_workshop_ids(text: str):
    tokens = re.split(r"[\s,]+", text)
    ids = []
    for t in tokens:
        t = t.strip()
        if not t: continue
        wid = extract_workshop_id(t)
        if wid: ids.append(wid)
    return list(dict.fromkeys(ids))

class WorkshopDownloaderThread(QThread):
    log_signal = pyqtSignal(str)
    done_signal = pyqtSignal()

    def __init__(self, wids, api_key, max_downloads, cellid, steam_integration, dest_path):
        super().__init__()
        self.wids = wids
        self.api_key = api_key
        self.max_downloads = max_downloads
        self.cellid = cellid
        self.steam_integration = steam_integration
        self.dest_path = dest_path
        
        # We use ACCELA's built-in DepotDownloader
        self.ddm_exe = str(Paths.deps("DepotDownloader.dll"))
        self.manifests_dir = os.path.join(get_base_path(), "manifests")
        self.keys_file = os.path.join(get_base_path(), "workshop_keys.txt")
        os.makedirs(self.manifests_dir, exist_ok=True)

    def log(self, msg):
        self.log_signal.emit(msg)

    def fetch_manifest(self, wid: str):
        try:
            r = requests.get(API_WORKSHOP.format(wid=wid), headers={"Authorization": f"Bearer {self.api_key}"}, timeout=30)
            r.raise_for_status()
        except Exception as e:
            self.log(f"  ✗ Manifest request failed: {e}")
            return None
        appid = r.headers.get("X-App-Id")
        manifest_id = r.headers.get("X-Manifest-Id")
        depot_key = r.headers.get("X-Depot-Key")
        if not appid or not manifest_id:
            self.log("  ✗ Missing required headers in manifest response.")
            return None
        manifest_path = os.path.join(self.manifests_dir, f"{appid}_{manifest_id}.manifest")
        with open(manifest_path, "wb") as f:
            f.write(r.content)
        return {"appid": appid, "manifest_id": manifest_id, "depot_key": depot_key, "manifest_path": manifest_path}

    def key_exists(self, appid: str):
        if not os.path.exists(self.keys_file): return False
        with open(self.keys_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith(f"{appid};"): return True
        return False

    def save_key(self, appid: str, key: str):
        with open(self.keys_file, "a", encoding="utf-8") as f:
            f.write(f"{appid};{key}\n")

    def _get_dir_size(self, path: str) -> int:
        total = 0
        for dirpath, _, filenames in os.walk(path):
            for fn in filenames:
                try: total += os.path.getsize(os.path.join(dirpath, fn))
                except OSError: pass
        return total

    def _parse_acf_block(self, text: str) -> dict:
        result = {}
        stack = [result]
        current_key = None
        for line in text.splitlines():
            s = line.strip()
            if not s or s.startswith("//"): continue
            tokens = re.findall(r'"[^"]*"|\{|\}', s)
            for tok in tokens:
                if tok == "{":
                    new = {}
                    if current_key is not None:
                        stack[-1][current_key] = new
                        stack.append(new)
                        current_key = None
                elif tok == "}":
                    if len(stack) > 1: stack.pop()
                else:
                    val = tok.strip('"')
                    if current_key is None: current_key = val
                    else:
                        stack[-1][current_key] = val
                        current_key = None
        return result

    def _write_acf(self, path: str, appid: str, items: dict):
        existing = {}
        root_meta = {}
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = f.read()
            parsed = self._parse_acf_block(raw)
            aw = parsed.get("AppWorkshop", {})
            root_meta = {k: v for k, v in aw.items() if k not in ("WorkshopItemsInstalled", "WorkshopItemDetails", "NeedsUpdate", "NeedsDownload") and isinstance(v, str)}
            installed = aw.get("WorkshopItemsInstalled", {})
            details = aw.get("WorkshopItemDetails", {})
            for wid, data in installed.items():
                existing[wid] = {"size": data.get("size", "0"), "timeupdated": data.get("timeupdated", "0"), "manifest": data.get("manifest", ""), "timetouched": details.get(wid, {}).get("timetouched", "0"), "subscribedby": details.get(wid, {}).get("subscribedby", "0")}
        for wid, info in items.items():
            existing[wid] = {"size": str(info["size"]), "timeupdated": str(info["timeupdated"]), "manifest": str(info["manifest"]), "timetouched": existing.get(wid, {}).get("timetouched", "0"), "subscribedby": existing.get(wid, {}).get("subscribedby", "0")}
        
        def q(v): return f'"{v}"'
        lines = ['"AppWorkshop"', '{', f'\t"appid"\t\t{q(appid)}']
        for k, v in root_meta.items():
            if k != "appid": lines.append(f'\t{q(k)}\t\t{q(v)}')
        lines.extend(['\t"NeedsUpdate"\t\t"0"', '\t"NeedsDownload"\t\t"0"', '\t"WorkshopItemsInstalled"', '\t{'])
        for wid, d in existing.items():
            lines.extend([f'\t\t{q(wid)}', '\t\t{', f'\t\t\t"size"\t\t{q(d["size"])}', f'\t\t\t"timeupdated"\t\t{q(d["timeupdated"])}', f'\t\t\t"manifest"\t\t{q(d["manifest"])}', '\t\t}'])
        lines.extend(['\t}', '\t"WorkshopItemDetails"', '\t{'])
        for wid, d in existing.items():
            lines.extend([f'\t\t{q(wid)}', '\t\t{', f'\t\t\t"manifest"\t\t{q(d["manifest"])}', f'\t\t\t"timeupdated"\t\t{q(d["timeupdated"])}', f'\t\t\t"timetouched"\t\t{q(d["timetouched"])}', f'\t\t\t"subscribedby"\t\t{q(d["subscribedby"])}', f'\t\t\t"latest_timeupdated"\t\t{q(d["timeupdated"])}', f'\t\t\t"latest_manifest"\t\t{q(d["manifest"])}', '\t\t}'])
        lines.extend(['\t}', '}'])
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def apply_steam_integration(self, appid: str, wid: str, manifest_id: str, mod_dir: str):
        acf_path = os.path.join(self.dest_path, "steamapps", "workshop", f"appworkshop_{appid}.acf")
        size = self._get_dir_size(mod_dir)
        now = int(time.time())
        try:
            self._write_acf(acf_path, appid, {wid: {"size": size, "timeupdated": now, "manifest": manifest_id}})
            self.log(f"  ✓ ACF updated → {acf_path}")
        except Exception as e:
            self.log(f"  ✗ Failed to update ACF: {e}")

    def run(self):
        for wid in self.wids:
            self.log(f"\n{'─' * 52}\n  Workshop ID : {wid}\n  → Fetching manifest...")
            info = self.fetch_manifest(wid)
            if not info:
                self.log("  ✗ Could not fetch manifest. Skipping.")
                continue

            appid = info["appid"]
            manifest_id = info["manifest_id"]
            depot_key = info["depot_key"]
            manifest_path = info["manifest_path"]

            self.log(f"  ✓ App ID     : {appid}\n  ✓ Manifest ID: {manifest_id}\n  ✓ Manifest   : {manifest_path}")

            if not depot_key:
                self.log("  ✗ No depot key in response. Skipping.")
                continue

            if not self.key_exists(appid):
                self.save_key(appid, depot_key)
                self.log(f"  ✓ Key saved  : {appid};{depot_key[:10]}…")
            else:
                self.log(f"  ✓ Depot key for App ID {appid} already cached.")

            if self.steam_integration and self.dest_path:
                out_dir = os.path.join(self.dest_path, "steamapps", "workshop", "content", appid, wid)
            else:
                out_dir = os.path.join(self.dest_path, "mods", appid, wid)

            # Use dotnet to run DepotDownloader.dll
            cmd = [
                "dotnet", self.ddm_exe,
                "-app", appid,
                "-ugc", wid,
                "-manifestfile", manifest_path,
                "-depotkeys", self.keys_file,
                "-dir", out_dir,
                "-max-downloads", str(self.max_downloads),
            ]
            if self.cellid:
                cmd += ["-cellid", str(self.cellid)]

            self.log(f"  → Running    : {' '.join(cmd)}")

            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
                for line in proc.stdout:
                    self.log(f"    {line.rstrip()}")
                proc.wait()
                if proc.returncode == 0:
                    self.log(f"  ✓ Download complete → {out_dir}")
                else:
                    self.log(f"  ✗ DepotDownloader exited with code {proc.returncode}.")
                    continue
            except Exception as e:
                self.log(f"  ✗ Failed to launch DepotDownloader: {e}")
                continue

            if self.steam_integration and self.dest_path:
                self.log("  → Applying Steam integration...")
                self.apply_steam_integration(appid, wid, manifest_id, out_dir)

        self.log(f"\n{'─' * 52}\n  All tasks finished.")
        self.done_signal.emit()

class WorkshopDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Workshop Downloader")
        self.resize(740, 620)
        self.settings = get_settings()
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # IDs
        ids_group = QGroupBox("Workshop IDs or Steam URLs (one per line, or comma-separated)")
        ids_layout = QVBoxLayout(ids_group)
        self.ids_input = QTextEdit()
        ids_layout.addWidget(self.ids_input)
        layout.addWidget(ids_group)

        # Options
        opts_layout = QHBoxLayout()
        opts_layout.addWidget(QLabel("Max downloads:"))
        self.max_dl = QSpinBox()
        self.max_dl.setRange(1, 1024)
        self.max_dl.setValue(8)
        opts_layout.addWidget(self.max_dl)
        opts_layout.addWidget(QLabel("Cell ID:"))
        self.cell_id = QLineEdit()
        opts_layout.addWidget(self.cell_id)
        
        # Steam Integration Checkbox inline
        self.steam_check = QCheckBox("Enable Steam Integration")
        opts_layout.addSpacing(20)
        opts_layout.addWidget(self.steam_check)
        
        opts_layout.addStretch()
        layout.addLayout(opts_layout)

        # Buttons
        btns_layout = QHBoxLayout()
        self.dl_btn = QPushButton("⬇ Download")
        self.dl_btn.clicked.connect(self._download)
        self.clear_btn = QPushButton("Clear Log")
        self.clear_btn.clicked.connect(self._clear_log)
        self.save_btn = QPushButton("💾 Save Settings")
        self.save_btn.clicked.connect(self._save_settings)
        self.status_label = QLabel()
        btns_layout.addWidget(self.dl_btn)
        btns_layout.addWidget(self.clear_btn)
        btns_layout.addWidget(self.save_btn)
        btns_layout.addWidget(self.status_label)
        btns_layout.addStretch()
        layout.addLayout(btns_layout)

        # Log
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: Consolas;")
        log_layout.addWidget(self.log_output)
        layout.addWidget(log_group)

    def _load_settings(self):
        self.steam_check.setChecked(self.settings.value("workshop_steam_enabled", False, type=bool))

    def _save_settings(self):
        self.settings.setValue("workshop_steam_enabled", self.steam_check.isChecked())
        self.status_label.setText("✓ Settings saved.")

    def _clear_log(self):
        self.log_output.clear()

    def _append_log(self, msg):
        self.log_output.append(msg)

    def _download(self):
        api_key = self.settings.value("morrenus_api_key", "", type=str)
        if not api_key:
            QMessageBox.warning(self, "No API Key", "Please enter your Hubcab API key in ACCELA Settings first.")
            return

        raw = self.ids_input.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "No IDs", "Please enter at least one Workshop ID or URL.")
            return

        wids = parse_workshop_ids(raw)
        if not wids:
            QMessageBox.warning(self, "No Valid IDs", "Could not parse any Workshop IDs from the input.")
            return

        max_downloads = self.max_dl.value()
        cellid = self.cell_id.text().strip()
        steam_integration = self.steam_check.isChecked()

        dest_path = ""
        if steam_integration:
            libraries = steam_helpers.get_steam_libraries()
            if libraries:
                auto_skip_single_choice = self.settings.value("auto_skip_single_choice", False, type=bool)
                if auto_skip_single_choice and len(libraries) == 1:
                    dest_path = libraries[0]
                else:
                    dialog = SteamLibraryDialog(libraries, self)
                    if dialog.exec():
                        dest_path = dialog.get_selected_path()
                    else:
                        return
            else:
                dest_path = QFileDialog.getExistingDirectory(self, "Select Steam Library Folder")
                if not dest_path:
                    return
        else:
            dest_path = QFileDialog.getExistingDirectory(self, "Select Destination Folder")
            if not dest_path:
                return

        self._save_settings()
        self.dl_btn.setEnabled(False)
        self.status_label.setText("⏳ Downloading…")

        try:
            self.thread = WorkshopDownloaderThread(wids, api_key, max_downloads, cellid, steam_integration, dest_path)
            self.thread.log_signal.connect(self._append_log)
            self.thread.done_signal.connect(self._on_done)
            self.thread.start()
        except Exception as e:
            self._append_log(f"💥 Failed to start download thread: {e}")
            import traceback
            self._append_log(traceback.format_exc())
            self._on_done()

    def _on_done(self):
        self.dl_btn.setEnabled(True)
        self.status_label.setText("✅ Done.")
