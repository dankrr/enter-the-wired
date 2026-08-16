import os
import sys
import logging
import signal
import subprocess
import time
import threading
from PyQt6.QtWidgets import QListWidgetItem, QMessageBox
from PyQt6.QtCore import Qt, QMetaObject, Q_ARG, QTimer, QObject

from core import steam_helpers

logger = logging.getLogger(__name__)


class JobQueueManager(QObject):
    def __init__(self, main_window):
        super().__init__(parent=main_window)
        self.main_window = main_window
        self.job_queue = []
        self.jobs_completed_count = 0
        self.steam_restart_prompt_pending = False
        self.is_showing_completion_dialog = False

    def add_job(self, file_path, metadata=None):
        """Add a job to the queue (Thread-Safe)"""
        if threading.current_thread() is not threading.main_thread():
            QMetaObject.invokeMethod(
                self.main_window,
                "add_job_safely",
                Qt.ConnectionType.QueuedConnection,
                Q_ARG(str, file_path),
            )
            return

        if not os.path.exists(file_path):
            logger.error(f"Failed to add job: file {file_path} does not exist.")
            QMessageBox.critical(
                self.main_window,
                "Error",
                f"Could not add job: File not found at {file_path}",
            )
            return

        job = {"path": file_path, "metadata": metadata or {}}
        self.job_queue.append(job)
        logger.info(f"Added new job to queue: {os.path.basename(file_path)}")

        self._update_ui_state()

        if not self.main_window.task_manager.is_processing:
            logger.info("Not processing, starting new job from queue.")
            self.main_window.log_output.clear()
            self._start_next_job()
        else:
            logger.info("App is busy, job added to queue.")

    def move_item_up(self):
        """Move selected queue item up"""
        current_row = self.main_window.ui_state.queue_list_widget.currentRow()
        if current_row > 0:
            item = self.job_queue.pop(current_row)
            self.job_queue.insert(current_row - 1, item)
            self._update_queue_display()
            self.main_window.ui_state.queue_list_widget.setCurrentRow(current_row - 1)

    def move_item_down(self):
        """Move selected queue item down"""
        current_row = self.main_window.ui_state.queue_list_widget.currentRow()
        if current_row != -1 and current_row < len(self.job_queue) - 1:
            item = self.job_queue.pop(current_row)
            self.job_queue.insert(current_row + 1, item)
            self._update_queue_display()
            self.main_window.ui_state.queue_list_widget.setCurrentRow(current_row + 1)

    def remove_item(self):
        """Remove selected queue item"""
        current_row = self.main_window.ui_state.queue_list_widget.currentRow()
        if current_row == -1:
            logger.debug("Remove item clicked, but no item is selected.")
            return

        try:
            removed_job = self.job_queue.pop(current_row)
            logger.info(
                f"Removed job from queue: {os.path.basename(removed_job['path'])}"
            )
            self._update_ui_state()

            if current_row < self.main_window.ui_state.queue_list_widget.count():
                self.main_window.ui_state.queue_list_widget.setCurrentRow(current_row)
            elif self.main_window.ui_state.queue_list_widget.count() > 0:
                self.main_window.ui_state.queue_list_widget.setCurrentRow(
                    current_row - 1
                )

        except Exception as e:
            logger.error(f"Error removing queue item: {e}", exc_info=True)

    def _start_next_job(self):
        """Start the next job in queue"""
        self._update_ui_state()

        if not self.job_queue:
            self._handle_queue_completion()
            return

        next_job = self.job_queue[0]
        file_path = next_job["path"]
        metadata = next_job.get("metadata", {})

        self.main_window.task_manager.start_zip_processing(file_path, metadata)

        self.job_queue.pop(0)
        self._update_ui_state()

    def _handle_queue_completion(self):
        """Handle when queue is empty"""
        if self.is_showing_completion_dialog:
            return

        self.is_showing_completion_dialog = True
        try:
            was_pending = self.steam_restart_prompt_pending
            self.steam_restart_prompt_pending = False

            if was_pending:
                from utils.settings import get_settings

                settings = get_settings()
                prompt_steam_restart = settings.value(
                    "prompt_steam_restart", True, type=bool
                )

                if prompt_steam_restart:
                    QTimer.singleShot(0, self._prompt_for_steam_restart)
                else:
                    logger.info(
                        "Steam restart prompt disabled by settings. Skipping prompt."
                    )
            elif self.jobs_completed_count > 0:
                QMessageBox.information(
                    self.main_window,
                    "Queue Finished",
                    f"All {self.jobs_completed_count} job(s) have finished successfully!",
                )

            self.jobs_completed_count = 0
        finally:
            self.is_showing_completion_dialog = False

    def _update_ui_state(self):
        """Update UI based on queue state"""
        if not self.main_window or not self.main_window.isVisible():
            return

        has_jobs = len(self.job_queue) > 0
        is_processing = self.main_window.task_manager.is_processing

        self.main_window.ui_state.update_queue_visibility(is_processing, has_jobs)
        self._update_queue_display()

    def _update_queue_display(self):
        """Update the queue list widget"""
        queue_list = self.main_window.ui_state.queue_list_widget
        queue_list.clear()

        for position, job in enumerate(self.job_queue, start=1):
            item = QListWidgetItem(
                f"{position}. {self._get_job_display_name(job)}"
            )
            item.setToolTip(job["path"])
            queue_list.addItem(item)

        self.main_window.ui_state.update_queue_summary(len(self.job_queue))

    @staticmethod
    def _get_job_display_name(job):
        """Prefer known game names while retaining a useful ZIP fallback."""
        metadata = job.get("metadata") or {}
        game_name = str(metadata.get("game_name") or "").strip()
        if game_name:
            return game_name

        filename = os.path.basename(job.get("path") or "")
        display_name, _ = os.path.splitext(filename)
        return display_name or filename or "Unknown download"

    def _check_if_safe_to_start_next_job(self):
        """Check if it's safe to start the next job"""
        if (
            not self.main_window.task_manager.is_processing
            and not self.main_window.task_manager.is_awaiting_zip_task_stop
            and not self.main_window.task_manager.is_awaiting_speed_monitor_stop
            and not self.main_window.task_manager.is_awaiting_download_stop
            and not self.main_window.task_manager.achievement_task_runner
        ):
            logger.debug("All thread cleanup flags are clear. Safe to start next job.")
            self._start_next_job()
        else:
            logger.debug(
                f"Not starting next job yet. State: "
                f"is_processing={self.main_window.task_manager.is_processing}, "
                f"awaiting_zip={self.main_window.task_manager.is_awaiting_zip_task_stop}, "
                f"awaiting_speed={self.main_window.task_manager.is_awaiting_speed_monitor_stop}, "
                f"awaiting_download={self.main_window.task_manager.is_awaiting_download_stop}, "
                f"achievement_runner={self.main_window.task_manager.achievement_task_runner is not None}"
            )

    def check_if_safe_to_start_next_job(self):
        self._check_if_safe_to_start_next_job()

    def _prompt_for_steam_restart(self):
        """Prompt user to restart Steam (Run via QTimer on Main Thread)"""
        reply = QMessageBox.question(
            self.main_window,
            "Restart Steam",
            "Steam-integrated changes were created. Would you like to restart Steam now to apply them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            logger.info("User agreed to restart Steam.")
            threading.Thread(target=self._perform_steam_restart, daemon=True).start()

    @staticmethod
    def _linux_steam_pids():
        """Find Steam client PIDs without requiring psutil."""
        pids = []
        try:
            entries = os.scandir("/proc")
        except OSError:
            return pids

        with entries:
            for entry in entries:
                if not entry.name.isdigit():
                    continue
                try:
                    with open(
                        os.path.join(entry.path, "comm"),
                        "r",
                        encoding="utf-8",
                        errors="ignore",
                    ) as handle:
                        if handle.read().strip().lower() == "steam":
                            pids.append(int(entry.name))
                except (OSError, ValueError):
                    continue
        return pids

    @classmethod
    def _wait_for_linux_steam_exit(cls, timeout=8.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not cls._linux_steam_pids():
                return True
            time.sleep(0.25)
        return not cls._linux_steam_pids()

    @classmethod
    def _stop_linux_steam_without_psutil(cls):
        """Stop Steam using native Linux interfaces when psutil is unavailable."""
        pids = cls._linux_steam_pids()
        if not pids:
            logger.info("Steam is already stopped.")
            return True

        # Ask Steam to shut down cleanly first so it can flush client state.
        try:
            subprocess.run(
                ["steam", "-shutdown"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            logger.debug("Steam -shutdown was unavailable; falling back to signals.")

        if cls._wait_for_linux_steam_exit(timeout=5.0):
            logger.info("Steam shut down cleanly.")
            return True

        pids = cls._linux_steam_pids()
        logger.info(f"Steam is still running; sending SIGTERM to {len(pids)} process(es).")
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            except OSError as exc:
                logger.debug(f"Could not terminate Steam PID {pid}: {exc}")

        if cls._wait_for_linux_steam_exit(timeout=4.0):
            logger.info("Steam stopped after SIGTERM.")
            return True

        pids = cls._linux_steam_pids()
        logger.warning(f"Steam is still running; forcing {len(pids)} process(es) to exit.")
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except OSError as exc:
                logger.debug(f"Could not kill Steam PID {pid}: {exc}")

        stopped = cls._wait_for_linux_steam_exit(timeout=3.0)
        if stopped:
            logger.info("Steam was stopped successfully.")
        return stopped

    def _perform_steam_restart(self):
        """Execute Steam restart logic in background thread"""
        try:
            if sys.platform == "linux":
                logger.info("Attempting to stop Steam...")

                if getattr(steam_helpers, "psutil", None) is not None:
                    stopped = steam_helpers.kill_steam_process()
                    if not stopped:
                        stopped = self._stop_linux_steam_without_psutil()
                else:
                    stopped = self._stop_linux_steam_without_psutil()

                if not stopped:
                    logger.warning("Could not stop Steam; aborting automatic restart.")
                    self._show_message_safe(
                        "Restart Failed",
                        "Could not stop Steam. Please restart it manually.",
                    )
                    return

                # Do not relaunch until the old client has actually exited.
                time.sleep(0.5)
                result = steam_helpers.start_steam()

                if result == "NEEDS_USER_PATH":
                    QMetaObject.invokeMethod(
                        self.main_window,
                        "handle_linux_steam_path_selection",
                        Qt.ConnectionType.QueuedConnection,
                    )
                elif result == "SUCCESS":
                    logger.info("Steam restarted successfully.")
                else:
                    logger.warning("Failed to start Steam.")
                    self._show_message_safe(
                        "Execution Failed",
                        "Could not start Steam.",
                    )

            else:
                steam_path = steam_helpers.find_steam_install()
                if steam_path:
                    logger.info("Closing Steam...")
                    if not steam_helpers.kill_steam_process():
                        logger.info(
                            "Steam process was not running or could not be killed."
                        )

                    time.sleep(1)

                    injector_path = os.path.join(steam_path, "DLLInjector.exe")
                    if os.path.exists(injector_path):
                        logger.info(
                            "Windows Wrapper Mode: Launching DLLInjector.exe..."
                        )
                        if not steam_helpers.run_dll_injector(steam_path):
                            self._show_message_safe(
                                "Injector Failed",
                                f"Could not launch DLLInjector.exe from {steam_path}.",
                            )
                    else:
                        user32_path = os.path.join(steam_path, "user32.dll")
                        if os.path.exists(user32_path):
                            logger.info(
                                "DLLInjector.exe not found, but user32.dll exists. Starting Steam normally..."
                            )
                            steam_helpers.start_steam()
                        else:
                            self._show_message_safe(
                                "Injector Not Found",
                                "DLLInjector.exe not found in Steam folder.",
                            )
                else:
                    self._show_message_safe(
                        "Error",
                        "Could not find Steam installation path.",
                    )

        except Exception as e:
            logger.error(f"Error during Steam restart: {e}", exc_info=True)

    @staticmethod
    def _show_message_safe(title, text):
        """Helper to show MessageBox from background thread"""
        logger.error(f"MSG: {title} - {text}")

    def clear(self):
        """Clear the job queue"""
        self.job_queue.clear()
        self._update_ui_state()
