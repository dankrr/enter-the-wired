"""
Theme Manager.

Handles application theming, palette application, and font loading.
"""

import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication

from utils.paths import Paths

logger = logging.getLogger(__name__)


def blend_color(base: QColor, overlay: QColor, amount: float) -> QColor:
    """Blend two colors without relying on QColor.lighter() for black tones."""
    amount = max(0.0, min(1.0, amount))
    inverse = 1.0 - amount
    return QColor(
        round(base.red() * inverse + overlay.red() * amount),
        round(base.green() * inverse + overlay.green() * amount),
        round(base.blue() * inverse + overlay.blue() * amount),
    )


def contrast_text_color(color: QColor) -> str:
    """Choose readable text for a filled accent control."""
    luminance = (
        color.red() * 0.299 + color.green() * 0.587 + color.blue() * 0.114
    )
    return "#09070A" if luminance >= 145 else "#FFFFFF"


def surface_colors(
    background: Union[str, QColor], accent: Union[str, QColor]
) -> Dict[str, str]:
    """Build the layered Wired palette used by application surfaces."""
    bg = QColor(background)
    accent_color = QColor(accent)
    if not bg.isValid():
        bg = QColor("#080608")
    if not accent_color.isValid():
        accent_color = QColor("#C06C84")

    white = QColor("#FFFFFF")
    neutral = QColor("#A89DA7")
    danger = QColor("#E7607D")

    return {
        "background": bg.name(),
        "background_deep": blend_color(bg, QColor("#000000"), 0.34).name(),
        "surface": blend_color(bg, accent_color, 0.055).name(),
        "surface_alt": blend_color(bg, accent_color, 0.105).name(),
        "surface_strong": blend_color(bg, accent_color, 0.17).name(),
        "accent_soft": blend_color(bg, accent_color, 0.24).name(),
        "border": blend_color(bg, accent_color, 0.38).name(),
        "border_hot": blend_color(bg, accent_color, 0.72).name(),
        "accent": accent_color.name(),
        "accent_light": blend_color(accent_color, white, 0.2).name(),
        "accent_text": contrast_text_color(accent_color),
        "text": blend_color(accent_color, white, 0.18).name(),
        "muted": blend_color(bg, neutral, 0.72).name(),
        "danger": danger.name(),
        "danger_surface": blend_color(bg, danger, 0.18).name(),
        "disabled": blend_color(bg, neutral, 0.32).name(),
    }


def normal_palette_colors(
    background_color: QColor, accent_color: QColor
) -> Dict[QPalette.ColorRole, QColor]:
    """Define colors for the normal palette state."""
    return {
        QPalette.ColorRole.Window: background_color,
        QPalette.ColorRole.WindowText: accent_color,
        QPalette.ColorRole.Base: background_color.darker(120),
        QPalette.ColorRole.AlternateBase: background_color,
        QPalette.ColorRole.ToolTipBase: accent_color,
        QPalette.ColorRole.ToolTipText: background_color,
        QPalette.ColorRole.Text: accent_color,
        QPalette.ColorRole.Button: background_color,
        QPalette.ColorRole.ButtonText: accent_color,
        QPalette.ColorRole.BrightText: accent_color.lighter(120),
        QPalette.ColorRole.Link: accent_color.lighter(120),
        QPalette.ColorRole.Highlight: accent_color,
        QPalette.ColorRole.HighlightedText: background_color,
        QPalette.ColorRole.PlaceholderText: accent_color.darker(120),
    }


def disabled_palette_colors(
    disabled_bg: QColor, disabled_text: QColor, background_color: QColor
) -> Dict[QPalette.ColorRole, QColor]:
    """Define colors for the disabled palette state."""
    return {
        QPalette.ColorRole.Button: disabled_bg,
        QPalette.ColorRole.ButtonText: disabled_text,
        QPalette.ColorRole.Text: disabled_text,
        QPalette.ColorRole.WindowText: disabled_text,
        QPalette.ColorRole.Base: background_color.darker(140),
    }


def apply_palette(app: QApplication, accent: str, background: str) -> None:
    """Apply the Fusion style and custom color palette to the application."""
    app.setStyle("Fusion")
    dark_palette = QPalette()

    background_color = QColor(background)
    accent_color = QColor(accent)

    disabled_bg = background_color.darker(200)
    disabled_text = QColor(100, 100, 100)

    # Apply normal colors
    for role, color in normal_palette_colors(background_color, accent_color).items():
        dark_palette.setColor(role, color)

    # Apply disabled colors
    for role, color in disabled_palette_colors(
        disabled_bg, disabled_text, background_color
    ).items():
        dark_palette.setColor(QPalette.ColorGroup.Disabled, role, color)

    app.setPalette(dark_palette)
    _apply_stylesheet(app, background_color, accent_color, disabled_bg, disabled_text)


def _apply_stylesheet(
    app: QApplication,
    bg_color: QColor,
    accent_color: QColor,
    disabled_bg: QColor,
    disabled_text: QColor,
) -> None:
    """Generate the layered Wired stylesheet used across every dialog."""
    colors = surface_colors(bg_color, accent_color)

    style_sheet = f"""
        QMainWindow, QDialog {{
            background-color: {colors['background']};
            color: {colors['text']};
        }}
        QWidget#AppRoot, QWidget#MainSurface, QWidget#BottomRegion {{
            background-color: {colors['background']};
        }}

        QLabel {{
            color: {colors['text']};
            background: transparent;
        }}
        QLabel#HeroTitle {{
            color: {colors['accent_light']};
            font-size: 20px;
            font-weight: 700;
        }}
        QLabel#EyebrowLabel, QLabel#SectionTitle {{
            color: {colors['muted']};
            font-size: 10px;
            font-weight: 700;
        }}
        QLabel#MutedLabel, QLabel#TelemetryLabel {{
            color: {colors['muted']};
        }}
        QLabel#StatusPill {{
            color: {colors['accent_light']};
            background-color: {colors['accent_soft']};
            border: 1px solid {colors['border']};
            border-radius: 9px;
            padding: 3px 8px;
            font-size: 9px;
            font-weight: 700;
        }}

        QFrame#DropCard, QFrame#ActivityCard, QFrame#QueueCard {{
            background-color: {colors['surface']};
            border: 1px solid {colors['border']};
            border-radius: 11px;
        }}
        QFrame#DropCard {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 {colors['surface_alt']},
                stop:0.52 {colors['surface']},
                stop:1 {colors['background_deep']}
            );
        }}
        QFrame#DropCard[dropActive="true"] {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 {colors['surface_strong']},
                stop:1 {colors['accent_soft']}
            );
            border: 2px solid {colors['accent']};
        }}
        QFrame#ActivityCard {{
            background-color: {colors['surface_alt']};
            border-color: {colors['border_hot']};
        }}
        QTextEdit#ActivityLog {{
            background-color: {colors['background_deep']};
            border-color: {colors['border']};
            color: {colors['muted']};
            font-family: monospace;
            font-size: 10px;
        }}
        QListWidget#QueueList {{
            background-color: {colors['background_deep']};
        }}

        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
        QSpinBox, QDoubleSpinBox {{
            background-color: {colors['surface']};
            color: {colors['text']};
            border: 1px solid {colors['border']};
            border-radius: 7px;
            padding: 8px 10px;
            selection-background-color: {colors['accent_soft']};
            selection-color: {colors['accent_light']};
        }}
        QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover,
        QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
            background-color: {colors['surface_alt']};
            border-color: {colors['border_hot']};
        }}
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
        QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 1px solid {colors['accent']};
        }}
        QComboBox::drop-down {{
            width: 24px;
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background-color: {colors['surface_alt']};
            color: {colors['text']};
            border: 1px solid {colors['border_hot']};
            selection-background-color: {colors['accent_soft']};
        }}

        QListWidget, QTreeWidget, QTableWidget {{
            background-color: {colors['background_deep']};
            color: {colors['text']};
            border: 1px solid {colors['border']};
            border-radius: 8px;
            outline: none;
            padding: 4px;
        }}
        QListWidget::item, QTreeWidget::item, QTableWidget::item {{
            color: {colors['text']};
            border-radius: 6px;
            padding: 8px;
            margin: 2px;
        }}
        QListWidget::item:hover, QTreeWidget::item:hover,
        QTableWidget::item:hover {{
            background-color: {colors['surface_alt']};
        }}
        QListWidget::item:selected, QTreeWidget::item:selected,
        QTableWidget::item:selected {{
            background-color: {colors['accent_soft']};
            color: {colors['accent_light']};
            border-left: 3px solid {colors['accent']};
        }}

        QPushButton {{
            background-color: {colors['surface_alt']};
            color: {colors['accent_light']};
            border: 1px solid {colors['border']};
            border-radius: 7px;
            padding: 8px 14px;
            min-height: 18px;
            font-weight: 700;
        }}
        QPushButton:hover {{
            background-color: {colors['surface_strong']};
            border-color: {colors['accent']};
            color: {colors['accent_light']};
        }}
        QPushButton:pressed {{
            background-color: {colors['accent_soft']};
            border-color: {colors['accent_light']};
        }}
        QPushButton#PrimaryButton {{
            background-color: {colors['accent']};
            color: {colors['accent_text']};
            border: 1px solid {colors['accent_light']};
        }}
        QPushButton#PrimaryButton:hover {{
            background-color: {colors['accent_light']};
            color: {colors['accent_text']};
        }}
        QPushButton#GhostButton {{
            background-color: transparent;
            border-color: {colors['border']};
            color: {colors['muted']};
        }}
        QPushButton#GhostButton:hover {{
            color: {colors['accent_light']};
            border-color: {colors['border_hot']};
        }}
        QPushButton#DangerButton {{
            background-color: {colors['danger_surface']};
            color: {colors['danger']};
            border-color: {colors['danger']};
        }}
        QPushButton#DangerButton:hover {{
            background-color: {colors['danger']};
            color: #FFFFFF;
        }}
        QPushButton#SmallButton {{
            padding: 6px 10px;
            min-height: 16px;
        }}
        QPushButton:disabled {{
            background-color: {colors['surface']};
            color: {colors['disabled']};
            border-color: {colors['surface_strong']};
            font-weight: 500;
        }}

        QCheckBox, QRadioButton {{
            color: {colors['text']};
            background: transparent;
            padding: 3px 2px;
            spacing: 8px;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 14px;
            height: 14px;
            background-color: {colors['background_deep']};
            border: 1px solid {colors['border_hot']};
        }}
        QCheckBox::indicator {{ border-radius: 3px; }}
        QRadioButton::indicator {{ border-radius: 7px; }}
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background-color: {colors['accent']};
            border-color: {colors['accent_light']};
        }}
        QCheckBox:disabled, QRadioButton:disabled {{
            color: {colors['muted']};
        }}
        QCheckBox::indicator:disabled, QRadioButton::indicator:disabled {{
            background-color: {colors['surface']};
            border-color: {colors['disabled']};
        }}

        QTabWidget::pane {{
            background-color: {colors['surface']};
            border: 1px solid {colors['border']};
            border-radius: 8px;
            top: -1px;
        }}
        QTabBar::tab {{
            background: transparent;
            color: {colors['muted']};
            border: none;
            border-bottom: 2px solid transparent;
            padding: 10px 14px;
        }}
        QTabBar::tab:hover {{ color: {colors['accent_light']}; }}
        QTabBar::tab:selected {{
            color: {colors['accent_light']};
            border-bottom-color: {colors['accent']};
        }}

        QGroupBox {{
            color: {colors['text']};
            background-color: {colors['surface']};
            border: 1px solid {colors['border']};
            border-radius: 8px;
            margin-top: 14px;
            padding: 12px 10px 10px 10px;
            font-weight: 700;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 10px;
            padding: 0 6px;
            color: {colors['accent_light']};
        }}

        QProgressBar {{
            background-color: {colors['background_deep']};
            border: 1px solid {colors['border']};
            border-radius: 5px;
            min-height: 9px;
            max-height: 9px;
            text-align: center;
        }}
        QProgressBar::chunk {{
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 {colors['accent']},
                stop:1 {colors['accent_light']}
            );
            border-radius: 4px;
        }}

        QScrollBar:vertical {{
            background: {colors['background_deep']};
            width: 10px;
            margin: 2px;
            border-radius: 5px;
        }}
        QScrollBar::handle:vertical {{
            background: {colors['border_hot']};
            min-height: 24px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {colors['accent']};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
        QScrollBar:horizontal {{
            background: {colors['background_deep']};
            height: 10px;
            margin: 2px;
            border-radius: 5px;
        }}
        QScrollBar::handle:horizontal {{
            background: {colors['border_hot']};
            min-width: 24px;
            border-radius: 4px;
        }}
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
            width: 0px;
        }}

        QMenu {{
            background-color: {colors['surface_alt']};
            color: {colors['text']};
            border: 1px solid {colors['border_hot']};
            border-radius: 6px;
            padding: 5px;
        }}
        QMenu::item {{ padding: 7px 18px; border-radius: 4px; }}
        QMenu::item:selected {{ background-color: {colors['accent_soft']}; }}

        QToolTip {{
            background-color: {colors['surface_alt']};
            color: {colors['accent_light']};
            border: 1px solid {colors['border_hot']};
            border-radius: 5px;
            padding: 6px 8px;
        }}
    """
    app.setStyleSheet(style_sheet)


def _resolve_font_path(font_resource: Union[str, Path]) -> Path:
    """Resolve the provided font resource to a concrete Path object."""
    try:
        if isinstance(font_resource, str):
            candidate = Path(font_resource)
            if candidate.is_absolute() and candidate.exists():
                return candidate
            return Paths.resource(font_resource)

        if isinstance(font_resource, Path):
            return font_resource

        return Paths.resource(str(font_resource))
    except TypeError:
        # Fallback for unexpected types
        return Paths.resource(str(font_resource))


def _load_and_set_font(
    app: QApplication, font_path: Path, current_font: Optional[QFont]
) -> Tuple[bool, str]:
    """Load a font file from disk and set it to the application."""
    logger.debug(f"Attempting to load font from: {font_path}")

    if not font_path.exists():
        logger.warning(f"Font file not found at: {font_path}")
        return False, str(font_path)

    font_id = QFontDatabase.addApplicationFont(str(font_path))
    if font_id == -1:
        logger.warning(f"QFontDatabase failed to load font: {font_path}")
        return False, str(font_path)

    families = QFontDatabase.applicationFontFamilies(font_id)
    if not families:
        logger.warning(f"No font families returned for: {font_path}")
        return False, str(font_path)

    font_name = families[0]

    if current_font:
        # Update existing font object with new family
        current_font.setFamily(font_name)
        new_font = current_font
    else:
        # Create new default font
        new_font = QFont(font_name, 10)

    app.setFont(new_font)
    return True, font_name


def apply_font(
    app: QApplication,
    font: Optional[QFont],
    font_file: Optional[Union[str, Path]],
) -> Tuple[bool, Union[str, Path]]:
    """
    Applies the font to the application.

    If font_file is provided, loads that font file and applies it.
    If font is provided (with a family name), checks if it's a system font.
    Otherwise, falls back to the default TrixieCyrG font.
    """
    default_font_file = "TrixieCyrG-Plain Regular.otf"

    # Case 1: Specific font file provided
    if font_file:
        path = _resolve_font_path(font_file)
        return _load_and_set_font(app, path, font)

    # Case 2: System font provided
    if font and font.family():
        font_family = font.family()
        if font_family in QFontDatabase.families():
            logger.debug(f"Using system font: {font_family}")
            app.setFont(font)
            return True, font_family

        # System font not found, log and fall through to default
        logger.debug(f"Font family '{font_family}' not found in system, using default")

    # Case 3: Fallback to default font
    path = _resolve_font_path(default_font_file)
    return _load_and_set_font(app, path, font)


def update_appearance(
    app: QApplication,
    accent: str = "#c36200",
    background: str = "#1f1f1f",
    font: Optional[QFont] = None,
    font_file: Optional[Union[str, Path]] = None,
) -> Tuple[bool, Union[str, Path]]:
    """
    Apply a dynamic palette and custom font to the application.

    Args:
        app: The QApplication instance.
        accent: Hex string for accent color.
        background: Hex string for background color.
        font: Optional QFont object for settings.
        font_file: Relative resource path to load custom font.
    """
    apply_palette(app, accent, background)
    return apply_font(app, font, font_file)
