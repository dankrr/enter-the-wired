import sys

from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.dialogs.settings import SettingsDialog as BaseSettingsDialog
from utils.helpers import create_checkbox_setting
from utils.runtime_status import get_runtime_status


class CleanSettingsDialog(BaseSettingsDialog):
    """Small usability layer over the upstream settings dialog."""

    def _create_downloads_tab(self) -> None:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        runtime = get_runtime_status()

        install_group = QGroupBox("Installation")
        install_layout = QVBoxLayout()

        library_tooltip = "Install games directly into one of your Steam libraries."
        if sys.platform == "linux":
            library_tooltip += " SLSsteam integration is applied automatically on Linux."

        self.library_mode_checkbox = create_checkbox_setting(
            "Install into Steam libraries",
            "library_mode",
            True,
            self,
            library_tooltip,
        )
        install_layout.addWidget(self.library_mode_checkbox)

        self.auto_skip_single_choice_checkbox = create_checkbox_setting(
            "Skip selection when there is only one choice",
            "auto_skip_single_choice",
            True,
            self,
            "Skip depot or library dialogs when ACCELA only has one valid option.",
        )
        install_layout.addWidget(self.auto_skip_single_choice_checkbox)

        max_layout = QHBoxLayout()
        max_label = QLabel("Parallel depot connections")
        max_label.setToolTip(
            "Maximum parallel DepotDownloader connections. This is not the number of queued games."
        )
        self.max_downloads_spinbox = QSpinBox()
        self.max_downloads_spinbox.setRange(1, 255)
        self.max_downloads_spinbox.setValue(
            self.settings.value("max_downloads", 16, type=int)
        )
        max_layout.addWidget(max_label)
        max_layout.addStretch()
        max_layout.addWidget(self.max_downloads_spinbox)
        install_layout.addLayout(max_layout)

        install_group.setLayout(install_layout)
        layout.addWidget(install_group)

        after_group = QGroupBox("After Download")
        after_layout = QVBoxLayout()
        after_layout.setSpacing(8)

        self.achievements_checkbox = create_checkbox_setting(
            "Generate Steam achievements",
            "generate_achievements",
            False,
            self,
            "Generate achievement files after a successful download.",
        )
        after_layout.addWidget(self.achievements_checkbox)
        self._apply_capability_state(
            after_layout, self.achievements_checkbox, runtime["slscheevo"]
        )

        self.steamless_checkbox = create_checkbox_setting(
            "Run Steamless",
            "use_steamless",
            False,
            self,
            "Run Steamless after a successful download.",
        )
        after_layout.addWidget(self.steamless_checkbox)
        self._apply_capability_state(
            after_layout, self.steamless_checkbox, runtime["steamless"]
        )

        self.steamless_aio_checkbox = create_checkbox_setting(
            "Run Steamless-AIO",
            "use_steamless_aio",
            False,
            self,
            "Use the Steamless-AIO alternative after a successful download.",
        )
        after_layout.addWidget(self.steamless_aio_checkbox)
        self._apply_capability_state(
            after_layout, self.steamless_aio_checkbox, runtime["steamless_aio"]
        )

        if sys.platform == "linux":
            self.application_shortcuts_checkbox = create_checkbox_setting(
                "Create application shortcuts",
                "create_application_shortcuts",
                False,
                self,
                "Create desktop shortcuts and fetch artwork from SteamGridDB.",
            )
            after_layout.addWidget(self.application_shortcuts_checkbox)

            sgdb_key = self.settings.value("sgdb_api_key", "", type=str).strip()
            shortcut_status = {
                "ready": bool(sgdb_key),
                "status": "Ready" if sgdb_key else "Needs SteamGridDB API key",
            }
            self._add_status_label(after_layout, shortcut_status)
        else:
            self.application_shortcuts_checkbox = None

        after_group.setLayout(after_layout)
        layout.addWidget(after_group)

        note = QLabel(
            "Unavailable optional tools are disabled instead of failing after the game finishes downloading."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(note)

        layout.addStretch()
        self.tab_widget.addTab(tab, "Downloads")

    def _apply_capability_state(self, layout, checkbox, capability: dict) -> None:
        if not capability.get("ready", False):
            checkbox.setChecked(False)
            checkbox.setEnabled(False)
        self._add_status_label(layout, capability)

    def _add_status_label(self, layout, capability: dict) -> None:
        ready = capability.get("ready", False)
        status = capability.get("status", "Unknown")
        color = "#7FC97F" if ready else self.accent_color

        row = QHBoxLayout()
        row.setContentsMargins(14, 0, 0, 2)
        label = QLabel(f"Status: {status}")
        label.setStyleSheet(f"color: {color}; font-size: 11px;")
        row.addWidget(label)
        row.addStretch()
        layout.addLayout(row)

    def _save_download_settings(self) -> None:
        super()._save_download_settings()
        self.settings.setValue(
            "use_steamless_aio",
            bool(
                self.steamless_aio_checkbox
                and self.steamless_aio_checkbox.isChecked()
            ),
        )
