import atexit
import logging
import sys
from collections import deque
from typing import Dict, Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import (
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QKeySequence,
    QMouseEvent,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
)

from components.custom_widgets import ScaledFontLabel, ScaledLabel
from managers.audio_manager import AudioManager
from managers.game_manager import GameManager
from managers.gif_manager import GIFManager
from managers.job_queue_manager import JobQueueManager
from managers.task_manager import TaskManager
from managers.ui_state_manager import UIStateManager
from ui.bottom_titlebar import BottomTitleBar
from ui.dialogs.credits import CreditsDialog
from ui.dialogs.fetchmanifest import FetchManifestDialog
from ui.dialogs.gamelibrary import GameLibraryDialog
from ui.dialogs.lain import LainMinigameDialog
from ui.dialogs.settings import SettingsDialog
from ui.dialogs.status import StatusDialog
from utils.logger import qt_log_handler
from utils.paths import Paths
from utils.settings import get_settings

logger = logging.getLogger(__name__)


class ResizeHandle(QWidget):
    """Transparent widget used to resize the frameless window."""

    def __init__(self, edge_name: str, main_window: "MainWindow"):
        super().__init__(main_window)
        self.edge_name = edge_name
        self.main_window = main_window
        self.resizing = False
        self.resize_start_pos = None
        self.resize_start_geom = None
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        window = self.main_window.windowHandle()
        edge = self._get_qt_edge()

        # Try system resize first (Wayland/Windows native)
        if window and window.isExposed() and window.startSystemResize(edge):
            event.accept()
            return

        # Fallback for X11/other
        self.resizing = True
        self.resize_start_pos = event.globalPosition().toPoint()
        self.resize_start_geom = self.main_window.geometry()
        self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self.resizing:
            return

        delta = event.globalPosition().toPoint() - self.resize_start_pos
        geom = self.resize_start_geom
        x, y, w, h = geom.x(), geom.y(), geom.width(), geom.height()

        if "right" in self.edge_name:
            w += delta.x()
        if "bottom" in self.edge_name:
            h += delta.y()
        if "left" in self.edge_name:
            x += delta.x()
            w -= delta.x()
        if "top" in self.edge_name:
            y += delta.y()
            h -= delta.y()

        w = max(w, self.main_window.minimumWidth())
        h = max(h, self.main_window.minimumHeight())

        self.main_window.setGeometry(x, y, w, h)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.resizing:
            self.releaseMouse()
            self.resizing = False
        event.accept()

    def _get_qt_edge(self) -> Qt.Edge:
        edge_map = {
            "left": Qt.Edge.LeftEdge,
            "right": Qt.Edge.RightEdge,
            "top": Qt.Edge.TopEdge,
            "bottom": Qt.Edge.BottomEdge,
            "top_left": Qt.Edge.LeftEdge,
            "top_right": Qt.Edge.RightEdge,
            "bottom_left": Qt.Edge.LeftEdge,
            "bottom_right": Qt.Edge.RightEdge,
        }
        return edge_map.get(self.edge_name, Qt.Edge.RightEdge)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.resize_handles: Dict[str, ResizeHandle] = {}
        self.key_sequence = deque(maxlen=4)
        self.target_sequence = ["l", "a", "i", "n"]
        self.settings = None
        self.accent_color = None
        self.background_color = None
        self.task_manager = None
        self.gif_manager = None
        self.ui_state = None
        self.job_queue = None
        self.audio_manager = None
        self.game_manager = None
        self.exit_shortcut = None
        self.sequence_timeout = None
        self.central_widget = None
        self.layout = None
        self.titlebar_position = None
        self.bottom_titlebar = None
        self.main_container = None
        self.main_layout = None
        self.drop_zone_container = None
        self.drop_zone_layout = None
        self.drop_zone_gif = None
        self.drop_text_label = None
        self.drop_hint_label = None
        self.idle_actions_widget = None
        self.choose_zip_button = None
        self.find_game_button = None
        self.library_button = None
        self.idle_log_button = None
        self.progress_container = None
        self.progress_layout = None
        self.progress_bar = None
        self.progress_meta_widget = None
        self.progress_label = None
        self.speed_label = None
        self.queue_summary_label = None
        self.bottom_widget = None
        self.bottom_layout = None
        self.log_output = None
        self.log_visible = False
        self.queue_panel_visible = False

        self._setup_window_properties()
        self._initialize_managers()
        self._setup_ui()
        self._setup_resize_handles()
        if self.ui_state:
            self.ui_state.apply_style_settings()
        self._setup_key_sequence_detector()
        self._setup_exit_shortcut()

    def _setup_window_properties(self) -> None:
        """Configure basic window properties."""
        self.setWindowTitle("ASSELA")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setGeometry(100, 100, 800, 600)

        icon_path = Paths.resource("logo/icon.ico")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        else:
            logger.warning(f"Could not find window icon at: {icon_path}")

        if sys.platform == "win32":
            MainWindow._setup_windows_taskbar()

    def _setup_exit_shortcut(self) -> None:
        """Setup Ctrl+Q shortcut to exit the application."""
        self.exit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self)
        self.exit_shortcut.activated.connect(self.close)
        logger.info("Ctrl+Q exit shortcut registered")

    def _setup_key_sequence_detector(self) -> None:
        """Setup key sequence detection for Easter egg."""
        self.sequence_timeout = QTimer(self)
        self.sequence_timeout.setSingleShot(True)
        self.sequence_timeout.timeout.connect(self.key_sequence.clear)

    def keyPressEvent(self, event) -> None:
        """Override keyPressEvent to detect key sequences."""
        key_text = event.text().lower()

        if key_text:
            self.key_sequence.append(key_text)
            # Reset sequence after 3 seconds of inactivity
            self.sequence_timeout.start(3000)

            if list(self.key_sequence) == self.target_sequence:
                self._on_lain_sequence_activated()
                self.key_sequence.clear()

        super().keyPressEvent(event)

    def _on_lain_sequence_activated(self) -> None:
        """Handle L->A->I->N sequence activation."""
        logger.info("LAIN sequence detected!")
        self.open_lain_minigame()

    def open_lain_minigame(self) -> None:
        """Open the Serial Experiments Lain minigame."""
        dialog = LainMinigameDialog(self)
        dialog.game_completed.connect(self.on_minigame_completed)
        dialog.exec()

    def on_minigame_completed(self, score: int) -> None:
        """Handle minigame completion."""
        logger.info(f"Lain minigame completed with score: {score}")
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("The Wired")
        msg_box.setText(f"Connection Terminated\n\nFinal Score: {score}")
        msg_box.exec()

    @staticmethod
    def _setup_windows_taskbar() -> None:
        """Windows-specific taskbar configuration."""
        try:
            import ctypes

            app_id = "god.is.in.the.wired.accela"
            # noinspection PyUnresolvedReferences
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except (ImportError, AttributeError) as e:
            logger.warning(f"Could not set AppUserModelID: {e}")

    def _initialize_managers(self) -> None:
        """Initialize all manager classes."""
        self.settings = get_settings()

        self.accent_color = self.settings.value("accent_color", "#C06C84")
        self.background_color = self.settings.value("background_color", "#000000")

        self.task_manager = TaskManager(self)
        self.gif_manager = GIFManager(self)
        self.ui_state = UIStateManager(self)
        self.job_queue = JobQueueManager(self)
        self.audio_manager = AudioManager(self)
        self.game_manager = GameManager(self)

        logger.info("Starting initial game library scan...")
        self.game_manager.scan_steam_libraries_async()

    def _setup_ui(self) -> None:
        """Setup the main UI components."""
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.titlebar_position = self.settings.value(
            "titlebar_position", "bottom", type=str
        )

        if self.titlebar_position == "top":
            self.bottom_titlebar = BottomTitleBar(self)
            self.layout.addWidget(self.bottom_titlebar)

        self._create_main_content()
        self._create_bottom_section()
        self.update_gif_display()

        if self.titlebar_position != "top":
            self.bottom_titlebar = BottomTitleBar(self)
            self.layout.addWidget(self.bottom_titlebar)

        self.setAcceptDrops(True)

    def _setup_resize_handles(self) -> None:
        """Setup invisible resize handles for all edges and corners."""
        edges = [
            "top_left",
            "top_right",
            "bottom_left",
            "bottom_right",
            "left",
            "right",
            "top",
            "bottom",
        ]

        for name in edges:
            handle = ResizeHandle(name, self)
            handle.setCursor(MainWindow._get_cursor_for_edge(name))
            self.resize_handles[name] = handle

        self._update_resize_handles_geometry()

    @staticmethod
    def _get_cursor_for_edge(edge: str) -> Qt.CursorShape:
        """Get appropriate cursor for each resize edge."""
        cursors = {
            "left": Qt.CursorShape.SizeHorCursor,
            "right": Qt.CursorShape.SizeHorCursor,
            "top": Qt.CursorShape.SizeVerCursor,
            "bottom": Qt.CursorShape.SizeVerCursor,
            "top_left": Qt.CursorShape.SizeFDiagCursor,
            "top_right": Qt.CursorShape.SizeBDiagCursor,
            "bottom_left": Qt.CursorShape.SizeBDiagCursor,
            "bottom_right": Qt.CursorShape.SizeFDiagCursor,
        }
        return cursors.get(edge, Qt.CursorShape.ArrowCursor)

    def _update_resize_handles_geometry(self) -> None:
        """Calculate and set geometry for all resize handles."""
        if not self.resize_handles:
            return

        w, h = self.width(), self.height()
        hw = 6  # Handle width

        # Define geometry calculations for each handle type
        geometries = {
            "top_left": (0, 0, hw, hw),
            "top_right": (w - hw, 0, hw, hw),
            "bottom_left": (0, h - hw, hw, hw),
            "bottom_right": (w - hw, h - hw, hw, hw),
            "left": (0, hw, hw, h - 2 * hw),
            "right": (w - hw, hw, hw, h - 2 * hw),
            "top": (hw, 0, w - 2 * hw, hw),
            "bottom": (hw, h - hw, w - 2 * hw, hw),
        }

        for name, (x, y, width, height) in geometries.items():
            if name in self.resize_handles:
                self.resize_handles[name].setGeometry(x, y, width, height)

    def resizeEvent(self, event) -> None:
        """Update resize handle positions when window is resized."""
        super().resizeEvent(event)
        self._update_resize_handles_geometry()

    def _create_main_content(self) -> None:
        """Create the main content area with drop zone."""
        self.main_container = QWidget()
        self.main_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.layout.addWidget(self.main_container, 3)

        self.main_layout = QVBoxLayout(self.main_container)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self._create_drop_zone()
        self._create_progress_section()

    def _create_drop_zone(self) -> None:
        """Create the drag and drop area."""
        self.drop_zone_container = QWidget()
        self.drop_zone_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self.drop_zone_layout = QVBoxLayout(self.drop_zone_container)
        self.drop_zone_layout.setContentsMargins(16, 8, 16, 8)
        self.drop_zone_layout.setSpacing(6)

        self.drop_zone_gif = ScaledLabel()
        self.drop_zone_gif.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone_gif.setMinimumHeight(150)
        self.drop_zone_gif.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        self.drop_text_label = ScaledFontLabel("Drop manifest ZIP here")
        self.drop_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_text_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.drop_text_label.setMinimumHeight(32)
        self.drop_text_label.setMaximumHeight(48)

        self.drop_hint_label = QLabel(
            "Choose a ZIP below, find a game, or review installed games and updates."
        )
        self.drop_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_hint_label.setWordWrap(True)

        self.idle_actions_widget = QWidget()
        idle_actions_layout = QHBoxLayout(self.idle_actions_widget)
        idle_actions_layout.setContentsMargins(0, 2, 0, 0)
        idle_actions_layout.setSpacing(8)
        idle_actions_layout.addStretch()

        self.choose_zip_button = QPushButton("Choose ZIP…")
        self.choose_zip_button.setToolTip("Add one or more manifest ZIPs")
        self.choose_zip_button.clicked.connect(self.open_zip_picker)
        idle_actions_layout.addWidget(self.choose_zip_button)

        self.find_game_button = QPushButton("Find a Game")
        self.find_game_button.setToolTip("Search for a game manifest")
        self.find_game_button.clicked.connect(self.open_fetch_dialog)
        idle_actions_layout.addWidget(self.find_game_button)

        self.library_button = QPushButton("Library && Updates")
        self.library_button.setToolTip("Review installed games and available updates")
        self.library_button.clicked.connect(self.open_game_library)
        idle_actions_layout.addWidget(self.library_button)

        self.idle_log_button = QPushButton("Activity Log")
        self.idle_log_button.setToolTip("Show technical download details")
        self.idle_log_button.clicked.connect(self.toggle_activity_log)
        idle_actions_layout.addWidget(self.idle_log_button)
        idle_actions_layout.addStretch()

        self.drop_zone_layout.addWidget(self.drop_zone_gif, 1)
        self.drop_zone_layout.addWidget(self.drop_text_label)
        self.drop_zone_layout.addWidget(self.drop_hint_label)
        self.drop_zone_layout.addWidget(self.idle_actions_widget)
        self.main_layout.addWidget(self.drop_zone_container, 10)

    def _create_progress_section(self) -> None:
        """Create the progress bar and compact activity summary."""
        self.progress_container = QWidget()
        self.progress_layout = QVBoxLayout(self.progress_container)
        self.progress_layout.setContentsMargins(20, 4, 20, 8)
        self.progress_layout.setSpacing(4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.valueChanged.connect(self._update_progress_label)
        self._update_progress_bar_style()
        self.progress_layout.addWidget(self.progress_bar)

        self.progress_meta_widget = QWidget()
        progress_meta_layout = QHBoxLayout(self.progress_meta_widget)
        progress_meta_layout.setContentsMargins(0, 0, 0, 0)
        progress_meta_layout.setSpacing(12)

        self.progress_label = QLabel("Progress · 0%")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        progress_meta_layout.addWidget(self.progress_label)

        self.speed_label = QLabel("Network speed · waiting")
        self.speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_label.setVisible(False)
        progress_meta_layout.addWidget(self.speed_label, 1)

        self.queue_summary_label = QLabel("Queue · 0 waiting")
        self.queue_summary_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        progress_meta_layout.addWidget(self.queue_summary_label)

        self.progress_meta_widget.setVisible(False)
        self.progress_layout.addWidget(self.progress_meta_widget)

        self.main_layout.addWidget(self.progress_container, 1)

    def _create_bottom_section(self) -> None:
        """Create the bottom section with queue and logs."""
        self.bottom_widget = QWidget()
        self.bottom_layout = QHBoxLayout(self.bottom_widget)
        self.bottom_layout.setContentsMargins(5, 5, 5, 5)

        self.ui_state.setup_queue_panel()
        self.bottom_layout.addWidget(self.ui_state.queue_widget, 1)

        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setPlaceholderText("Technical activity will appear here.")
        self.log_output.setVisible(False)
        qt_log_handler.new_record.connect(self.log_output.append)
        self.bottom_layout.addWidget(self.log_output, 1)

        self.layout.addWidget(self.bottom_widget, 1)
        self.ui_state.queue_widget.setVisible(False)
        self.bottom_widget.setVisible(False)

    def _update_progress_label(self, value: int) -> None:
        """Keep an accessible percentage beside the slim progress bar."""
        if self.progress_label:
            self.progress_label.setText(f"Progress · {value}%")

    def set_queue_count(self, count: int) -> None:
        """Show the number of jobs waiting behind the active download."""
        if self.queue_summary_label:
            self.queue_summary_label.setText(f"Queue · {count} waiting")

    def set_queue_panel_visible(self, visible: bool) -> None:
        """Show or hide the queue without affecting the optional activity log."""
        self.queue_panel_visible = visible
        if visible and self.height() < 360:
            self.resize(self.width(), 360)
        if self.ui_state and self.ui_state.queue_widget:
            self.ui_state.queue_widget.setVisible(visible)
        self._update_bottom_panel_visibility()

    def toggle_activity_log(self) -> None:
        """Keep diagnostics available without making them the main interface."""
        self.log_visible = not self.log_visible
        if self.log_visible and self.height() < 400:
            self.resize(self.width(), 400)
        self._update_bottom_panel_visibility()

    def _update_bottom_panel_visibility(self) -> None:
        if not self.bottom_widget or not self.log_output:
            return

        self.log_output.setVisible(self.log_visible)
        self.bottom_widget.setVisible(self.queue_panel_visible or self.log_visible)

        button_text = "Hide Activity Log" if self.log_visible else "Activity Log"
        if self.idle_log_button:
            self.idle_log_button.setText(button_text)
        if self.ui_state and self.ui_state.queue_log_button:
            self.ui_state.queue_log_button.setText(button_text)

    def show_idle_state(self) -> None:
        """Restore the welcoming drop target after the queue finishes."""
        self.drop_text_label.setText("Drop manifest ZIP here")
        self.drop_hint_label.setText(
            "Choose a ZIP below, find a game, or review installed games and updates."
        )
        self.idle_actions_widget.setVisible(True)
        self.progress_bar.setVisible(False)
        self.progress_meta_widget.setVisible(False)
        self.speed_label.setVisible(False)

    def show_queued_state(self) -> None:
        """Show the brief handoff state before a queued job starts."""
        self.drop_text_label.setText("Download queued")
        self.drop_hint_label.setText("Preparing the next manifest ZIP…")
        self.idle_actions_widget.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setText("Progress · waiting")
        self.progress_meta_widget.setVisible(True)
        self.speed_label.setVisible(False)

    def show_active_state(self) -> None:
        """Switch the drop target into a focused active-job view."""
        self.idle_actions_widget.setVisible(False)
        self.progress_meta_widget.setVisible(True)

    def set_activity(self, game_name: str, detail: str) -> None:
        """Present normal job status without requiring the activity log."""
        self.show_active_state()
        self.drop_text_label.setText(game_name or "Preparing download")
        self.drop_hint_label.setText(detail)

    def set_activity_detail(self, detail: str) -> None:
        if self.drop_hint_label:
            self.drop_hint_label.setText(detail)

    def set_download_speed(self, speed_text: str) -> None:
        """Normalize the worker's speed text for the compact summary row."""
        value = speed_text.removeprefix("Download Speed:").strip()
        self.speed_label.setText(f"Network speed · {value}")

    def open_zip_picker(self) -> None:
        """Offer a keyboard-friendly alternative to dragging manifest ZIPs."""
        zip_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose Manifest ZIPs",
            "",
            "Manifest ZIPs (*.zip)",
        )
        for zip_path in zip_paths:
            self.job_queue.add_job(zip_path)

    def update_gif_display(self, enabled: Optional[bool] = None) -> None:
        """Update GIF display visibility and adjust window layout."""
        if enabled is None:
            enabled = self.settings.value("gif_display_enabled", True, type=bool)

        if enabled:
            if self.height() < 400:
                self.resize(self.width(), max(400, self.height()))
            self.main_layout.setStretchFactor(self.drop_zone_gif, 9)
            self.drop_zone_gif.setVisible(True)
            self.layout.setStretchFactor(self.main_container, 3)
            self.layout.setStretchFactor(self.bottom_widget, 1)
        else:
            current_height = self.height()
            gif_height = self.drop_zone_gif.height()
            new_height = max(200, current_height - gif_height)
            self.resize(self.width(), new_height)
            self.main_layout.setStretchFactor(self.drop_zone_gif, 0)
            self.drop_zone_gif.setVisible(False)
            self.layout.setStretchFactor(self.main_container, 1)
            self.layout.setStretchFactor(self.bottom_widget, 3)

        self.update()
        logger.info(f"GIF display updated: {'enabled' if enabled else 'disabled'}")

    def update_progress_bar_style(self) -> None:
        self._update_progress_bar_style()

    def _update_progress_bar_style(self) -> None:
        """Update progress bar styling."""
        self.progress_bar.setStyleSheet(
            f"""
            QProgressBar {{
                max-height: 10px;
                border: 1px solid {self.accent_color};
                border-radius: 5px;
                text-align: center;
                color: #FFFFFF;
            }}
            QProgressBar::chunk {{
                background-color: {self.accent_color};
                border-radius: 5px;
            }}
        """
        )

    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        dialog.exec()

    def open_fetch_dialog(self) -> None:
        self.ui_state.fetch_dialog = FetchManifestDialog(self)
        self.ui_state.fetch_dialog.exec()
        self.ui_state.fetch_dialog = None

    def open_workshop_dialog(self) -> None:
        from ui.dialogs.workshop import WorkshopDialog
        dialog = WorkshopDialog(self)
        dialog.exec()

    def open_game_library(self) -> None:
        dialog = GameLibraryDialog(self)
        dialog.exec()

    def open_status_dialog(self) -> None:
        dialog = StatusDialog(self)
        dialog.exec()

    def open_credits_dialog(self) -> None:
        dialog = CreditsDialog(self)
        dialog.exec()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if not event.mimeData().hasUrls():
            return

        urls = event.mimeData().urls()
        has_zip = any(
            url.isLocalFile() and url.toLocalFile().lower().endswith(".zip")
            for url in urls
        )

        if has_zip:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        urls = event.mimeData().urls()
        new_jobs = [
            url.toLocalFile()
            for url in urls
            if url.isLocalFile() and url.toLocalFile().lower().endswith(".zip")
        ]

        if not new_jobs:
            return

        logger.info(f"Added {len(new_jobs)} file(s) to the queue via drag-drop.")
        for job_path in new_jobs:
            self.job_queue.add_job(job_path)

    def closeEvent(self, event) -> None:
        """Handle application shutdown."""
        try:
            MainWindow._cleanup_logging()
            self.task_manager.cleanup()
            self.job_queue.clear()
            self.game_manager.cleanup()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        super().closeEvent(event)

    def reposition_titlebar(self, position: str) -> None:
        """Dynamically reposition the titlebar without restart."""
        if not hasattr(self, "bottom_titlebar") or not self.bottom_titlebar:
            return

        self.layout.removeWidget(self.bottom_titlebar)
        self.bottom_titlebar.setParent(None)

        if position == "top":
            self.layout.insertWidget(0, self.bottom_titlebar)
        else:
            self.layout.addWidget(self.bottom_titlebar)

        self.titlebar_position = position
        logger.info(f"Titlebar repositioned to: {position}")

    @staticmethod
    def _cleanup_logging() -> None:
        """Clean up logging system."""
        try:
            atexit.unregister(logging.shutdown)
            logging.getLogger().removeHandler(qt_log_handler)
            qt_log_handler.close()
            logger.info("QtLogHandler removed and atexit hook unregistered.")
            logging.shutdown()
        except Exception as e:
            print(f"Error during custom logger shutdown: {e}")
