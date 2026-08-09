import logging
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from components.custom_widgets import ScaledFontLabel, ScaledLabel
from utils.logger import open_log_directory
from utils.runtime_status import get_runtime_status
from utils.settings import get_settings

logger = logging.getLogger(__name__)


class StatusDialog(QDialog):
    """Show runtime health and status for the last install task."""

    STATUS_OK = "#7FC97F"
    STATUS_IN_PROGRESS = "#FFA500"
    STATUS_ERROR = "#FF5C5C"

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.parent_window = parent
        self.settings = get_settings()
        self.accent_color = self.settings.value("accent_color", "#C06C84")

        self.setWindowTitle("ACCELA Status")
        self.resize(520, 460)
        self.setMinimumSize(460, 380)

        self.runtime_layout = None
        self.task_layout = None
        self.runtime_rows = []

        self.ddm_status = self.accent_color
        self.ddm_status_text = "Not run"
        self.slscheevo_status = self.accent_color
        self.slscheevo_status_text = "Not run"
        self.steamless_status = self.accent_color
        self.steamless_status_text = "Not run"
        self.last_game_name = "No game installed"

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 14, 14, 14)
        self.layout.setSpacing(10)

        self._gather_task_status()
        self._setup_ui()
        logger.debug("StatusDialog initialized.")

    def _gather_task_status(self) -> None:
        """Gather the last install status from TaskManager."""
        if not self.parent_window or not hasattr(self.parent_window, "task_manager"):
            return

        task_manager = self.parent_window.task_manager
        status = task_manager.get_component_status()
        status_map = {
            "ok": self.STATUS_OK,
            "in_progress": self.STATUS_IN_PROGRESS,
            "error": self.STATUS_ERROR,
            "not_run": self.accent_color,
        }

        self.ddm_status = status_map.get(status["ddm_status"], self.accent_color)
        self.ddm_status_text = status["ddm_status_text"]
        self.slscheevo_status = status_map.get(
            status["slscheevo_status"], self.accent_color
        )
        self.slscheevo_status_text = status["slscheevo_status_text"]
        self.steamless_status = status_map.get(
            status["steamless_status"], self.accent_color
        )
        self.steamless_status_text = status["steamless_status_text"]
        self.last_game_name = task_manager.last_installed_game or "No game installed"

    def _setup_ui(self) -> None:
        title = ScaledFontLabel("ACCELA Status")
        title.setStyleSheet("font-size: 14pt;")
        self.layout.addWidget(title)

        hint = QLabel(
            "Core runtime checks are local. Optional tools can be missing without "
            "breaking downloads or game launches."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888888; font-size: 11px;")
        self.layout.addWidget(hint)

        self._create_runtime_group()
        self._create_last_task_group()
        self.layout.addStretch()
        self._create_footer_buttons()

    def _create_runtime_group(self) -> None:
        group = QGroupBox("Runtime Health")
        self.runtime_layout = QVBoxLayout(group)
        self.runtime_layout.setSpacing(5)
        self._refresh_runtime_rows()
        self.layout.addWidget(group)

    def _refresh_runtime_rows(self) -> None:
        if self.runtime_layout is None:
            return

        while self.runtime_layout.count():
            item = self.runtime_layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget:
                widget.deleteLater()
            elif child_layout:
                self._clear_layout(child_layout)

        runtime = get_runtime_status()
        order = (
            "steam",
            "slssteam",
            "depot_downloader",
            "steam_api",
            "dotnet",
            "slscheevo",
            "steamless",
            "steamless_aio",
        )

        for key in order:
            entry = runtime[key]
            ready = entry["ready"]
            required = entry["required"]
            if ready:
                color = self.STATUS_OK
            elif required:
                color = self.STATUS_ERROR
            else:
                color = self.accent_color

            self.runtime_layout.addLayout(
                self._create_status_row(entry["label"], color, entry["status"])
            )

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child = item.layout()
            if widget:
                widget.deleteLater()
            elif child:
                StatusDialog._clear_layout(child)

    def _create_last_task_group(self) -> None:
        group = QGroupBox("Last Install")
        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(5)

        game_label = ScaledLabel(self.last_game_name)
        game_label.setStyleSheet("font-size: 10pt")
        group_layout.addWidget(game_label)

        group_layout.addLayout(
            self._create_status_row(
                "Download Manager", self.ddm_status, self.ddm_status_text
            )
        )
        group_layout.addLayout(
            self._create_status_row(
                "Achievements", self.slscheevo_status, self.slscheevo_status_text
            )
        )
        group_layout.addLayout(
            self._create_status_row(
                "DRM Removal", self.steamless_status, self.steamless_status_text
            )
        )

        self.layout.addWidget(group)

    def _create_footer_buttons(self) -> None:
        button_layout = QHBoxLayout()

        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self._refresh_runtime_rows)
        button_layout.addWidget(refresh_button)

        logs_button = QPushButton("Open Logs")
        logs_button.clicked.connect(open_log_directory)
        button_layout.addWidget(logs_button)

        button_layout.addStretch()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        button_layout.addWidget(buttons)
        self.layout.addLayout(button_layout)

    @staticmethod
    def _create_status_row(name: str, color: str, status_text: str) -> QHBoxLayout:
        row_layout = QHBoxLayout()

        indicator = QLabel()
        indicator.setFixedSize(10, 10)
        indicator.setStyleSheet(f"border-radius: 5px; background-color: {color};")

        name_label = ScaledLabel(name)
        name_label.setMinimumWidth(175)

        status_label = ScaledLabel(status_text)
        status_label.setStyleSheet("color: #AAAAAA;")

        row_layout.addWidget(indicator)
        row_layout.addWidget(name_label)
        row_layout.addStretch()
        row_layout.addWidget(status_label, alignment=Qt.AlignmentFlag.AlignRight)
        return row_layout
