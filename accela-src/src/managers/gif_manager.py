import hashlib
import json
import logging
import os
import shutil
from pathlib import Path

from utils.helpers import get_base_path
from utils.paths import Paths

logger = logging.getLogger(__name__)


class GIFManager:
    """Keep ACCELA GIF assets ready without forcing image-processing deps.

    Core mode copies the original GIFs. Accent-color recoloring is loaded from
    managers.gif_colorizer only when NumPy and Pillow are installed.
    """

    def __init__(self, main_window):
        self.main_window = main_window
        self.settings = main_window.settings
        self.disable_color_gifs = self.settings.value(
            "disable_color_gifs", False, type=bool
        )
        self.regenerate_anyway = False
        self._warned_missing_colorizer = False

    def process_gif_batch(self, output_dir, accent_color):
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        color_subdir = output_dir / accent_color.lstrip("#")
        color_subdir.mkdir(parents=True, exist_ok=True)

        sources = self._find_unique_gifs(
            [get_base_path() / "gifs" / "custom", Paths.resource("gif")]
        )
        if not sources:
            logger.warning("No GIF files found")
            return

        colorize = self._get_colorizer()
        wants_color = not self.disable_color_gifs
        use_color = wants_color and colorize is not None

        state_path = color_subdir / ".gif-state.json"
        state = self._load_state(state_path)
        new_state = {}
        changed = 0

        for gif_name, source_path in sources.items():
            target_path = color_subdir / gif_name
            source_hash = self._sha256(source_path)
            expected = {
                "source": source_hash,
                "accent": accent_color,
                "colorized": use_color,
            }

            if (
                self.regenerate_anyway
                or not target_path.exists()
                or state.get(gif_name) != expected
            ):
                try:
                    if use_color:
                        colorize(source_path, target_path, accent_color)
                    else:
                        shutil.copy2(source_path, target_path)
                    changed += 1
                except Exception as exc:
                    logger.warning(
                        "GIF processing failed for %s; using original (%s)",
                        gif_name,
                        exc,
                    )
                    shutil.copy2(source_path, target_path)
                    expected["colorized"] = False

            new_state[gif_name] = expected
            self._link_or_copy(target_path, output_dir / gif_name)

        self._save_state(state_path, new_state)
        self.regenerate_anyway = False

        mode = "colorized" if use_color else "original"
        logger.info(
            "GIF assets ready: %d total, %d updated, mode=%s",
            len(sources),
            changed,
            mode,
        )

    def _get_colorizer(self):
        if self.disable_color_gifs:
            return None

        try:
            from managers.gif_colorizer import colorize_gif

            return colorize_gif
        except ImportError as exc:
            if not self._warned_missing_colorizer:
                logger.info(
                    "Optional GIF recoloring is unavailable; using original GIFs (%s)",
                    exc,
                )
                self._warned_missing_colorizer = True
            return None

    @staticmethod
    def _find_unique_gifs(input_dirs):
        found = {}
        for input_dir in input_dirs:
            input_dir = Path(input_dir)
            if not input_dir.exists():
                logger.debug("GIF directory does not exist: %s", input_dir)
                continue

            for path in sorted(input_dir.glob("*.gif")):
                found.setdefault(path.name, path)
        return found

    @staticmethod
    def _sha256(path):
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _load_state(path):
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _save_state(path, state):
        temp_path = path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
        temp_path.replace(path)

    @staticmethod
    def _link_or_copy(target_path, visible_path):
        try:
            if visible_path.is_symlink() or visible_path.exists():
                visible_path.unlink()

            if os.name == "nt":
                shutil.copy2(target_path, visible_path)
            else:
                relative_target = os.path.relpath(target_path, visible_path.parent)
                visible_path.symlink_to(relative_target)
        except OSError:
            shutil.copy2(target_path, visible_path)
