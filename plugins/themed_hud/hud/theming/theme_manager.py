"""
HUD Theme Manager and QSS Stylesheet Presets.
Compatible with Python 2.7 and Python 3.x.
"""

import os

THEME_CLASSIC = "classic"
THEME_FROSTED = "frosted-dark"
THEME_MINIMAL = "minimal-transparent"
THEME_HIGH_CONTRAST = "high-contrast"

THEME_ALIASES = {
    "classic": THEME_CLASSIC,
    "light": THEME_CLASSIC,
    "frosted": THEME_FROSTED,
    "frosted-dark": THEME_FROSTED,
    "dark": THEME_FROSTED,
    "minimal": THEME_MINIMAL,
    "minimal-transparent": THEME_MINIMAL,
    "transparent": THEME_MINIMAL,
    "high-contrast": THEME_HIGH_CONTRAST,
    "contrast": THEME_HIGH_CONTRAST,
    "high contrast": THEME_HIGH_CONTRAST,
}

PRESET_THEMES = {
    THEME_CLASSIC: """
        QMainWindow, QWidget {
            background-color: #f0f0f0;
            color: #000000;
        }
        QTextEdit {
            background-color: #ffffff;
            color: #000000;
            border: none;
            border-radius: 0px;
            font-family: 'Segoe UI', Arial, sans-serif;
            min-height: 0px;
            margin: 0px;
        }
        QTreeView, QListWidget {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #dcdcdc;
            selection-background-color: #3498db;
            selection-color: #ffffff;
        }
        QHeaderView::section {
            background-color: #e4e4e4;
            color: #000000;
            padding: 4px;
            border: 1px solid #dcdcdc;
            font-weight: bold;
        }
        QPushButton {
            background-color: #e0e0e0;
            color: #000000;
            border: 1px solid #cccccc;
            padding: 4px 10px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #d0d0d0;
        }
        QLineEdit {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #cccccc;
            padding: 3px;
        }
        QMenu {
            background-color: #f0f0f0;
            color: #000000;
            border: 1px solid #cccccc;
            padding: 4px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 9pt;
        }
        QMenu::item {
            background-color: transparent;
            padding: 5px 24px 5px 12px;
            border-radius: 2px;
        }
        QMenu::item:selected {
            background-color: #3498db;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background-color: #dcdcdc;
            margin: 4px 6px;
        }
    """,
    THEME_FROSTED: """
        QMainWindow, QWidget {
            background-color: #1e1e24;
            color: #f8f9fa;
        }
        QTextEdit {
            background-color: #18181c;
            color: #e9ecef;
            border: none;
            border-radius: 0px;
            font-family: 'Segoe UI', Arial, sans-serif;
            min-height: 0px;
            margin: 0px;
        }
        QTreeView, QListWidget {
            background-color: #18181c;
            color: #e9ecef;
            border: 1px solid #2b2b36;
            selection-background-color: #4a5568;
            selection-color: #ffffff;
        }
        QHeaderView::section {
            background-color: #2b2b36;
            color: #60a5fa;
            padding: 4px;
            border: 1px solid #3b3b4a;
            font-weight: bold;
        }
        QPushButton {
            background-color: #2b2b36;
            color: #f8f9fa;
            border: 1px solid #3b3b4a;
            padding: 4px 10px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #3b3b4a;
        }
        QLineEdit {
            background-color: #18181c;
            color: #f8f9fa;
            border: 1px solid #3b3b4a;
            padding: 3px;
        }
        QMenu {
            background-color: #1e1e24;
            color: #f8f9fa;
            border: 1px solid #3b3b4a;
            padding: 4px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 9pt;
        }
        QMenu::item {
            background-color: transparent;
            padding: 5px 24px 5px 12px;
            border-radius: 2px;
        }
        QMenu::item:selected {
            background-color: #2563eb;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background-color: #3b3b4a;
            margin: 4px 6px;
        }
    """,
    THEME_MINIMAL: """
        QMainWindow, QWidget {
            background-color: #111111;
            color: #e0e0e0;
        }
        QTextEdit {
            background-color: #000000;
            color: #f5f5f5;
            border: none;
            border-radius: 0px;
            font-family: 'Segoe UI', Arial, sans-serif;
            min-height: 0px;
            margin: 0px;
        }
        QTreeView, QListWidget {
            background-color: #000000;
            color: #f5f5f5;
            border: 1px solid #333333;
            selection-background-color: #222222;
            selection-color: #3498db;
        }
        QHeaderView::section {
            background-color: #1a1a1a;
            color: #93c5fd;
            padding: 4px;
            border: 1px solid #333333;
            font-weight: bold;
        }
        QPushButton {
            background-color: #1a1a1a;
            color: #e0e0e0;
            border: 1px solid #333333;
            padding: 4px 10px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #2a2a2a;
        }
        QLineEdit {
            background-color: #000000;
            color: #e0e0e0;
            border: 1px solid #333333;
            padding: 3px;
        }
        QMenu {
            background-color: #111111;
            color: #e0e0e0;
            border: 1px solid #333333;
            padding: 4px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 9pt;
        }
        QMenu::item {
            background-color: transparent;
            padding: 5px 24px 5px 12px;
            border-radius: 2px;
        }
        QMenu::item:selected {
            background-color: #2563eb;
            color: #ffffff;
        }
        QMenu::separator {
            height: 1px;
            background-color: #333333;
            margin: 4px 6px;
        }
    """,
    THEME_HIGH_CONTRAST: """
        QMainWindow, QWidget {
            background-color: #000000;
            color: #ffffff;
        }
        QTextEdit {
            background-color: #000000;
            color: #ffffff;
            border: none;
            border-radius: 0px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-weight: bold;
            min-height: 0px;
            margin: 0px;
        }
        QTreeView, QListWidget {
            background-color: #000000;
            color: #ffffff;
            border: 2px solid #ffffff;
            selection-background-color: #ffffff;
            selection-color: #000000;
        }
        QHeaderView::section {
            background-color: #000000;
            color: #ffffff;
            padding: 4px;
            border: 2px solid #ffffff;
            font-weight: bold;
        }
        QPushButton {
            background-color: #000000;
            color: #ffffff;
            border: 2px solid #ffffff;
            padding: 4px 10px;
            border-radius: 0px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #ffffff;
            color: #000000;
        }
        QLineEdit {
            background-color: #000000;
            color: #ffffff;
            border: 2px solid #ffffff;
            padding: 3px;
        }
        QMenu {
            background-color: #000000;
            color: #ffffff;
            border: 2px solid #ffffff;
            padding: 4px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 9pt;
            font-weight: bold;
        }
        QMenu::item {
            background-color: transparent;
            padding: 5px 24px 5px 12px;
        }
        QMenu::item:selected {
            background-color: #ffffff;
            color: #000000;
            font-weight: bold;
        }
        QMenu::separator {
            height: 2px;
            background-color: #ffffff;
            margin: 4px 6px;
        }
    """,
}

BUILTIN_THEME_DATA = {
    THEME_CLASSIC: {
        "name": "Classic",
        "background_color": "#f0f0f0",
        "textedit_bg": "#ffffff",
        "text_color": "#000000",
        "accent_color": "#3498db",
        "border_color": "#cccccc",
        "cmd_color": "blue",
        "sys_color": "purple",
        "err_color": "red",
        "background_opacity": 1.0,
        "text_opacity": 1.0,
        "opacity": 1.0,
        "text_alignment": "left",
    },
    THEME_FROSTED: {
        "name": "Frosted Dark",
        "background_color": "#1e1e24",
        "textedit_bg": "#18181c",
        "text_color": "#f8f9fa",
        "accent_color": "#2563eb",
        "border_color": "#3b3b4a",
        "cmd_color": "#3498db",
        "sys_color": "#9b59b6",
        "err_color": "#e74c3c",
        "background_opacity": 0.95,
        "text_opacity": 1.0,
        "opacity": 0.95,
        "text_alignment": "left",
    },
    THEME_MINIMAL: {
        "name": "Minimal Transparent",
        "background_color": "#111111",
        "textedit_bg": "#000000",
        "text_color": "#e0e0e0",
        "accent_color": "#2563eb",
        "border_color": "#333333",
        "cmd_color": "#93c5fd",
        "sys_color": "#c084fc",
        "err_color": "#f87171",
        "background_opacity": 0.75,
        "text_opacity": 1.0,
        "opacity": 0.85,
        "text_alignment": "left",
    },
    THEME_HIGH_CONTRAST: {
        "name": "High Contrast",
        "background_color": "#000000",
        "textedit_bg": "#000000",
        "text_color": "#ffffff",
        "accent_color": "#ffffff",
        "border_color": "#ffffff",
        "cmd_color": "#00ffff",
        "sys_color": "#ffff00",
        "err_color": "#ff0000",
        "background_opacity": 1.0,
        "text_opacity": 1.0,
        "opacity": 1.0,
        "text_alignment": "left",
    },
}

CUSTOM_THEMES_FILE = os.path.expanduser("~/.caster/hud_custom_themes.json")


def color_to_qss(color_val, opacity=1.0):
    """
    Converts any color string (#RRGGBB, #RGB, named color, or rgba)
    combined with opacity float (0.0 to 1.0) into a standard QSS color string.
    If opacity >= 0.999 and color_val is not an rgba string, returns as-is.
    """
    op = max(0.0, min(1.0, float(opacity)))
    s = str(color_val).strip()
    if op >= 0.999 and not s.lower().startswith("rgba"):
        return s

    alpha_int = int(round(op * 255))
    if s.lower().startswith("rgba") and "(" in s and ")" in s:
        parts = s[s.find("(") + 1 : s.find(")")].split(",")
        if len(parts) >= 3:
            try:
                r = int(parts[0].strip())
                g = int(parts[1].strip())
                b = int(parts[2].strip())
                return "rgba({0}, {1}, {2}, {3})".format(r, g, b, alpha_int)
            except Exception:
                pass
    try:
        from castervoice.lib.qt import QtGui
        qc = QtGui.QColor(s)
        if qc.isValid():
            return "rgba({0}, {1}, {2}, {3})".format(qc.red(), qc.green(), qc.blue(), alpha_int)
    except Exception:
        pass
    return s


def build_stylesheet(data):
    """
    Generates a full Qt QSS stylesheet string dynamically from a theme data dictionary.
    Supports distinct background_opacity and text_opacity (letter opacity).
    """
    bg_raw = data.get("background_color", "#1e1e24")
    txt_bg_raw = data.get("textedit_bg", bg_raw)
    txt_raw = data.get("text_color", "#f8f9fa")
    accent_raw = data.get("accent_color", "#2563eb")
    border_raw = data.get("border_color", "#3b3b4a")

    bg_op = float(data.get("background_opacity", data.get("opacity", 1.0)))
    txt_op = float(data.get("text_opacity", 1.0))

    bg = color_to_qss(bg_raw, bg_op)
    txt_bg = color_to_qss(txt_bg_raw, bg_op)
    txt = color_to_qss(txt_raw, txt_op)
    accent = color_to_qss(accent_raw, 1.0)
    border = color_to_qss(border_raw, max(0.3, bg_op))

    return """
        QMainWindow, QWidget {{
            background-color: {bg};
            color: {txt};
        }}
        QTextEdit {{
            background-color: {txt_bg};
            color: {txt};
            border: none;
            border-radius: 0px;
            font-family: 'Segoe UI', Arial, sans-serif;
            min-height: 0px;
            margin: 0px;
        }}
        QTreeView, QListWidget {{
            background-color: {txt_bg};
            color: {txt};
            border: 1px solid {border};
            selection-background-color: {accent};
            selection-color: #ffffff;
        }}
        QHeaderView::section {{
            background-color: {border};
            color: {accent};
            padding: 4px;
            border: 1px solid {border};
            font-weight: bold;
        }}
        QPushButton {{
            background-color: {border};
            color: {txt};
            border: 1px solid {border};
            padding: 4px 10px;
            border-radius: 3px;
        }}
        QPushButton:hover {{
            background-color: {accent};
            color: #ffffff;
        }}
        QLineEdit {{
            background-color: {txt_bg};
            color: {txt};
            border: 1px solid {border};
            padding: 3px;
        }}
        QMenu {{
            background-color: {bg};
            color: {txt};
            border: 1px solid {border};
            padding: 4px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 9pt;
        }}
        QMenu::item {{
            background-color: transparent;
            padding: 5px 24px 5px 12px;
            border-radius: 2px;
        }}
        QMenu::item:selected {{
            background-color: {accent};
            color: #ffffff;
        }}
        QMenu::separator {{
            height: 1px;
            background-color: {border};
            margin: 4px 6px;
        }}
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 8px;
            margin: 0px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {border};
            min-height: 20px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {accent};
        }}
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            height: 0px;
        }}
    """.format(bg=bg, txt_bg=txt_bg, txt=txt, accent=accent, border=border)


class ThemeManager(object):
    """
    Manages HUD appearance themes, user-created palettes, and QSS stylesheets.
    """

    _custom_themes_cache = None
    _custom_file_path = CUSTOM_THEMES_FILE

    @classmethod
    def set_custom_file_path(cls, path):
        """Allows test suites to override the custom themes file location."""
        cls._custom_file_path = path
        cls._custom_themes_cache = None

    @classmethod
    def normalize_theme_name(cls, theme_name):
        """Converts user input/alias to canonical theme name."""
        if not theme_name:
            return THEME_CLASSIC
        cleaned = str(theme_name).lower().strip()
        if cleaned in THEME_ALIASES:
            return THEME_ALIASES[cleaned]
        customs = cls.load_custom_themes()
        for k in customs.keys():
            if k.lower() == cleaned:
                return k
        return cleaned

    @classmethod
    def is_builtin_theme(cls, theme_name):
        """Returns True if theme is one of the built-in presets."""
        norm = cls.normalize_theme_name(theme_name)
        return norm in BUILTIN_THEME_DATA

    @classmethod
    def load_custom_themes(cls):
        """Loads and returns all user-created custom themes dictionary."""
        if cls._custom_themes_cache is not None:
            return cls._custom_themes_cache

        cls._custom_themes_cache = {}
        if os.path.isfile(cls._custom_file_path):
            try:
                import json
                with open(cls._custom_file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        cls._custom_themes_cache = data
            except Exception:
                cls._custom_themes_cache = {}

        return cls._custom_themes_cache

    @classmethod
    def save_custom_theme(cls, name, theme_data):
        """
        Saves or updates a custom theme configuration.
        """
        customs = cls.load_custom_themes()
        theme_id = str(name).strip().lower().replace(" ", "-")
        data = dict(theme_data)
        data["name"] = str(name).strip()
        customs[theme_id] = data
        cls._custom_themes_cache = customs

        try:
            import json
            dir_name = os.path.dirname(cls._custom_file_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)
            with open(cls._custom_file_path, "w", encoding="utf-8") as f:
                json.dump(customs, f, indent=2)
        except Exception:
            pass

        return theme_id

    @classmethod
    def delete_custom_theme(cls, name):
        """Deletes a custom theme (built-in themes cannot be deleted)."""
        if cls.is_builtin_theme(name):
            return False

        theme_id = cls.normalize_theme_name(name)
        customs = cls.load_custom_themes()
        if theme_id in customs:
            del customs[theme_id]
            cls._custom_themes_cache = customs
            try:
                import json
                with open(cls._custom_file_path, "w", encoding="utf-8") as f:
                    json.dump(customs, f, indent=2)
            except Exception:
                pass
            return True
        return False

    @classmethod
    def get_theme_data(cls, theme_name):
        """
        Returns structured dictionary of theme colors and properties.
        """
        norm = cls.normalize_theme_name(theme_name)
        if norm in BUILTIN_THEME_DATA:
            return dict(BUILTIN_THEME_DATA[norm])

        customs = cls.load_custom_themes()
        if norm in customs:
            return dict(customs[norm])

        # Fallback
        return dict(BUILTIN_THEME_DATA[THEME_CLASSIC])

    @classmethod
    def get_theme_colors(cls, theme_name):
        """
        Returns history text colors (cmd_color, sys_color, err_color),
        adjusted for text_opacity (letter opacity).
        """
        data = cls.get_theme_data(theme_name)
        txt_op = float(data.get("text_opacity", 1.0))
        cmd_raw = data.get("cmd_color", "#3498db")
        sys_raw = data.get("sys_color", "#9b59b6")
        err_raw = data.get("err_color", "#e74c3c")
        return {
            "cmd_color": color_to_qss(cmd_raw, txt_op),
            "sys_color": color_to_qss(sys_raw, txt_op),
            "err_color": color_to_qss(err_raw, txt_op),
        }

    @classmethod
    def get_stylesheet(cls, theme_name, background_opacity=None, text_opacity=None):
        """Returns the complete QSS stylesheet string for the requested theme."""
        norm = cls.normalize_theme_name(theme_name)
        theme_data = cls.get_theme_data(norm)
        if background_opacity is not None:
            theme_data["background_opacity"] = float(background_opacity)
        if text_opacity is not None:
            theme_data["text_opacity"] = float(text_opacity)

        bg_op = float(theme_data.get("background_opacity", theme_data.get("opacity", 1.0)))
        txt_op = float(theme_data.get("text_opacity", 1.0))

        # Built-in presets at default opacities
        if norm in PRESET_THEMES and bg_op >= 0.999 and txt_op >= 0.999 and background_opacity is None and text_opacity is None:
            return PRESET_THEMES[norm]

        # Dynamic build for custom themes or overridden opacities
        customs = cls.load_custom_themes()
        if norm in customs or norm in BUILTIN_THEME_DATA or background_opacity is not None or text_opacity is not None:
            return build_stylesheet(theme_data)

        # Check optional external .qss file in ~/.caster/themes/<name>.qss
        external_path = os.path.expanduser("~/.caster/themes/{0}.qss".format(norm))
        if os.path.isfile(external_path):
            try:
                with open(external_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                pass

        return PRESET_THEMES.get(norm, PRESET_THEMES[THEME_CLASSIC])

    @classmethod
    def get_available_themes(cls):
        """Returns a list of all canonical theme names (built-in and custom)."""
        themes = [THEME_CLASSIC, THEME_FROSTED, THEME_MINIMAL, THEME_HIGH_CONTRAST]
        customs = cls.load_custom_themes()
        for k in sorted(customs.keys()):
            if k not in themes:
                themes.append(k)

        # External .qss themes
        themes_dir = os.path.expanduser("~/.caster/themes")
        if os.path.isdir(themes_dir):
            try:
                for fname in sorted(os.listdir(themes_dir)):
                    if fname.endswith(".qss"):
                        stem = os.path.splitext(fname)[0]
                        if stem not in themes:
                            themes.append(stem)
            except Exception:
                pass

        return themes
