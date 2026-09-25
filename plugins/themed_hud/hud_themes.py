"""
HUD Theme Engine for Caster Heads-Up Display.

Provides built-in Qt Style Sheet (QSS) presets and custom user stylesheet
loading for the Caster HUD.
"""

from pathlib import Path
from castervoice.lib import settings

THEME_CLASSIC = "classic"
THEME_FROSTED_DARK = "frosted-dark"
THEME_MINIMAL_TRANSPARENT = "minimal-transparent"
THEME_HIGH_CONTRAST = "high-contrast"

BUILTIN_THEMES = {
    THEME_CLASSIC: """
        QTextEdit {
            background-color: #ffffff;
            color: #000000;
            min-height: 0px;
            min-width: 0px;
            margin: 0px;
            padding: 1px 2px;
        }
    """,
    THEME_FROSTED_DARK: """
        QMainWindow, QWidget {
            background-color: #1a1d24;
            color: #e4e7eb;
            font-family: 'Segoe UI', 'SF Pro Display', Arial, sans-serif;
        }
        QTextEdit {
            background-color: #21252e;
            color: #d1d5db;
            border: 1px solid #323846;
            border-radius: 4px;
            min-height: 0px;
            min-width: 0px;
            margin: 0px;
            padding: 1px 2px;
            selection-background-color: #2980b9;
            selection-color: #ffffff;
        }
        QScrollBar:vertical {
            border: none;
            background: #1a1d24;
            width: 8px;
            margin: 0px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical {
            background: #374151;
            min-height: 20px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background: #4b5563;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QTreeView {
            background-color: #21252e;
            color: #e4e7eb;
            border: 1px solid #323846;
            border-radius: 6px;
            gridline-color: #323846;
            padding: 4px;
        }
        QHeaderView::section {
            background-color: #111827;
            color: #60a5fa;
            border: 1px solid #323846;
            padding: 4px 8px;
            font-weight: bold;
        }
        QMenu {
            background-color: #1a1d24;
            color: #e4e7eb;
            border: 1px solid #323846;
            border-radius: 4px;
            padding: 4px;
        }
        QMenu::item {
            padding: 6px 20px;
            border-radius: 4px;
        }
        QMenu::item:selected {
            background-color: #2980b9;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background-color: #323846;
            margin: 4px 8px;
        }
    """,
    THEME_MINIMAL_TRANSPARENT: """
        QMainWindow, QWidget {
            background-color: rgba(20, 24, 30, 200);
            color: #f3f4f6;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        QTextEdit {
            background-color: rgba(20, 24, 30, 200);
            color: #f3f4f6;
            border: 1px solid rgba(255, 255, 255, 30);
            border-radius: 4px;
            min-height: 0px;
            min-width: 0px;
            margin: 0px;
            padding: 1px 2px;
        }
        QScrollBar:vertical {
            border: none;
            background: transparent;
            width: 6px;
        }
        QScrollBar::handle:vertical {
            background: rgba(255, 255, 255, 50);
            border-radius: 3px;
        }
        QTreeView {
            background-color: rgba(26, 29, 36, 220);
            color: #f3f4f6;
            border: 1px solid #374151;
            border-radius: 6px;
            gridline-color: #374151;
            padding: 4px;
        }
        QHeaderView::section {
            background-color: #111827;
            color: #60a5fa;
            border: 1px solid #374151;
            padding: 4px 8px;
            font-weight: bold;
        }
        QMenu {
            background-color: #1a1d24;
            color: #e4e7eb;
            border: 1px solid #323846;
            border-radius: 4px;
            padding: 4px;
        }
        QMenu::item:selected {
            background-color: #2980b9;
            color: #ffffff;
        }
    """,
    THEME_HIGH_CONTRAST: """
        QMainWindow, QWidget {
            background-color: #000000;
            color: #ffff00;
            font-family: Consolas, 'Courier New', monospace;
            font-weight: bold;
        }
        QTextEdit {
            background-color: #000000;
            color: #ffff00;
            border: 2px solid #ffff00;
            min-height: 0px;
            min-width: 0px;
            margin: 0px;
            padding: 1px 2px;
        }
        QScrollBar:vertical {
            background: #000000;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background: #ffff00;
            min-height: 20px;
        }
        QTreeView {
            background-color: #000000;
            color: #00ffff;
            border: 2px solid #00ffff;
            padding: 4px;
        }
        QHeaderView::section {
            background-color: #000000;
            color: #ffff00;
            border: 1px solid #ffff00;
            padding: 4px 8px;
            font-weight: bold;
        }
        QMenu {
            background-color: #000000;
            color: #ffff00;
            border: 2px solid #ffff00;
        }
        QMenu::item:selected {
            background-color: #ffff00;
            color: #000000;
        }
    """,
}


def get_available_themes():
    """Return a list of available theme names (built-in and custom)."""
    theme_names = list(BUILTIN_THEMES.keys())
    user_dir = settings.SETTINGS.get("paths", {}).get("USER_DIR") if settings.SETTINGS else None
    if user_dir:
        themes_dir = Path(user_dir).joinpath("themes")
        if themes_dir.is_dir():
            for f in themes_dir.glob("*.qss"):
                if f.stem not in theme_names:
                    theme_names.append(f.stem)
    return theme_names


def get_theme_stylesheet(theme_name):
    """
    Get the QSS stylesheet string for the requested theme name.
    Falls back to built-in presets, custom .qss files, or empty string for classic.
    """
    if not theme_name or theme_name == THEME_CLASSIC:
        return ""

    if theme_name in BUILTIN_THEMES:
        return BUILTIN_THEMES[theme_name]

    # Check custom themes directory in user dir
    user_dir = settings.SETTINGS.get("paths", {}).get("USER_DIR") if settings.SETTINGS else None
    if user_dir:
        custom_theme_path = Path(user_dir).joinpath("themes", "{}.qss".format(theme_name))
        if custom_theme_path.is_file():
            try:
                with open(custom_theme_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass

    return BUILTIN_THEMES.get(THEME_FROSTED_DARK, "")
