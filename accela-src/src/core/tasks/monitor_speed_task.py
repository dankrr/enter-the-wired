import logging
import os
import sys
import time

from PyQt6.QtCore import QObject, pyqtSignal

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


class SpeedMonitorTask(QObject):
    speed_update = pyqtSignal(str)

    def __init__(self, interval=1):
        super().__init__()
        self.interval = interval
        self._is_running = True

    def run(self):
        if not self.is_available():
            logger.info("Network activity monitoring is unavailable on this platform.")
            return

        logger.info("Speed monitor task starting.")
        try:
            last_bytes = self._get_received_bytes()
        except Exception as e:
            logger.error(f"Could not initialize network activity monitoring: {e}")
            return

        while self._is_running:
            time.sleep(self.interval)
            if not self._is_running:
                break
            try:
                current_bytes = self._get_received_bytes()
                speed = (current_bytes - last_bytes) / self.interval
                last_bytes = current_bytes
                self.speed_update.emit(
                    f"Download Speed: {SpeedMonitorTask._format_speed(speed)}"
                )
            except Exception as e:
                logger.warning(f"Error during speed update loop: {e}")
                self.stop()

        logger.info("Speed monitor task finished.")

    @staticmethod
    def is_available() -> bool:
        """Return whether a supported network counter is available."""
        return psutil is not None or (
            sys.platform.startswith("linux") and os.path.isfile("/proc/net/dev")
        )

    @staticmethod
    def _get_received_bytes() -> int:
        if psutil is not None:
            return int(psutil.net_io_counters().bytes_recv)

        if sys.platform.startswith("linux"):
            total = 0
            with open("/proc/net/dev", "r", encoding="utf-8") as handle:
                for line in handle:
                    if ":" not in line:
                        continue
                    _, counters = line.split(":", 1)
                    fields = counters.split()
                    if fields:
                        total += int(fields[0])
            return total

        raise RuntimeError("No supported network counter is available")

    @staticmethod
    def _format_speed(speed_bps):
        if speed_bps < 1024:
            return f"{speed_bps:.2f} B/s"
        if speed_bps < 1024**2:
            return f"{(speed_bps / 1024):.2f} KB/s"
        return f"{(speed_bps / 1024**2):.2f} MB/s"

    def stop(self):
        logger.debug("Stop signal received by speed monitor.")
        self._is_running = False
