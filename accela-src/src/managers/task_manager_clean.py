import logging
import sys

from PyQt6.QtCore import pyqtSlot

from managers.task_manager import TaskManager as BaseTaskManager
from utils.runtime_status import get_runtime_status
from utils.yaml_config_manager import is_slssteam_mode_enabled

logger = logging.getLogger(__name__)


class CleanTaskManager(BaseTaskManager):
    """TaskManager layer that keeps optional post-processing genuinely optional."""

    @pyqtSlot()
    def _finalize_job_logic(self):
        if self._should_prompt_for_steam_restart():
            self.main_window.job_queue.steam_restart_prompt_pending = True

        runtime = get_runtime_status()

        steamless_enabled = self.settings.value("use_steamless", False, type=bool)
        steamless_aio_enabled = self.settings.value(
            "use_steamless_aio", False, type=bool
        )
        steamless_key = "steamless_aio" if steamless_aio_enabled else "steamless"

        if (steamless_enabled or steamless_aio_enabled) and not self.is_cancelling:
            if "steamless" not in self._job_steps_completed:
                self._job_steps_completed.add("steamless")
                if runtime[steamless_key]["ready"]:
                    self.main_window.drop_text_label.setText(
                        f"Running Steamless: {self.game_data.get('game_name', '')}"
                    )
                    self._start_steamless_processing(use_aio=steamless_aio_enabled)
                    return

                logger.info(
                    "%s requested but its runtime is unavailable; skipping.",
                    runtime[steamless_key]["label"],
                )
                self._last_steamless_status = "not_run"
                self._last_steamless_status_text = "Unavailable"

        shortcuts_enabled = self.settings.value(
            "create_application_shortcuts", False, type=bool
        )
        slssteam_mode = is_slssteam_mode_enabled()

        if (
            shortcuts_enabled
            and slssteam_mode
            and sys.platform == "linux"
            and not self.is_cancelling
        ):
            if "shortcuts_linux" not in self._job_steps_completed:
                self._job_steps_completed.add("shortcuts_linux")
                self._start_application_shortcuts_step()
                return

        achievements_enabled = self.settings.value(
            "generate_achievements", False, type=bool
        )
        if achievements_enabled and not self.is_cancelling:
            if "achievements" not in self._job_steps_completed:
                self._job_steps_completed.add("achievements")
                if runtime["slscheevo"]["ready"]:
                    self.main_window.drop_text_label.setText(
                        f"Generating Achievements: {self.game_data.get('game_name', '')}"
                    )
                    self._start_achievement_generation()
                    return

                logger.info(
                    "Achievement generation requested but SLScheevo is unavailable; skipping."
                )
                self._last_slscheevo_status = "not_run"
                self._last_slscheevo_status_text = "Unavailable"

        if (
            shortcuts_enabled
            and not self.is_cancelling
            and "shortcuts_linux" not in self._job_steps_completed
        ):
            if "shortcuts_std" not in self._job_steps_completed:
                self._job_steps_completed.add("shortcuts_std")
                self._start_application_shortcuts_step()
                return

        logger.info("All post-processing steps complete. Finishing job.")
        self.main_window.job_queue.jobs_completed_count += 1
        if not self.is_cancelling:
            self.main_window.game_manager.scan_steam_libraries_async()

        self.job_finished()
