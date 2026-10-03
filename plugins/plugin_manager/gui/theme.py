# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
QSS Stylesheet and design tokens for Caster Plugin Manager UI.
"""

COLOR_BG_WINDOW = "#1e1e2e"
COLOR_BG_PANEL = "#252538"
COLOR_BG_HOVER = "#313244"
COLOR_BG_SELECTED = "#45475a"
COLOR_BG_INPUT = "#181825"
COLOR_BORDER = "#3b3d54"
COLOR_TEXT_PRIMARY = "#cdd6f4"
COLOR_TEXT_MUTED = "#a6adc8"
COLOR_ACCENT = "#89b4fa"
COLOR_ACCENT_HOVER = "#b4befe"

# Health state indicator colors
COLOR_HEALTH_READY = "#2ecc71"
COLOR_HEALTH_DISABLED = "#7f8c8d"
COLOR_HEALTH_WARNING = "#f39c12"
COLOR_HEALTH_ERROR = "#e74c3c"


def get_health_color(health_state: str) -> str:
    """Returns corresponding hex color code for a given PluginHealthState value."""
    mapping = {
        "ready": COLOR_HEALTH_READY,
        "disabled": COLOR_HEALTH_DISABLED,
        "missing_dependencies": COLOR_HEALTH_WARNING,
        "incompatible_platform": COLOR_HEALTH_ERROR,
        "malformed_metadata": COLOR_HEALTH_ERROR,
        "load_error": COLOR_HEALTH_ERROR,
    }
    return mapping.get(str(health_state).lower(), COLOR_HEALTH_DISABLED)


def get_stylesheet() -> str:
    """Returns compiled QSS stylesheet string for PluginManagerWindow."""
    return f"""
    QDialog, QWidget {{
        background-color: {COLOR_BG_WINDOW};
        color: {COLOR_TEXT_PRIMARY};
        font-family: 'Segoe UI', Arial, sans-serif;
        font-size: 13px;
    }}

    /* Header Bar & Search Input */
    QLineEdit {{
        background-color: {COLOR_BG_INPUT};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 13px;
        selection-background-color: {COLOR_ACCENT};
        selection-color: {COLOR_BG_WINDOW};
    }}
    QLineEdit:focus {{
        border: 1px solid {COLOR_ACCENT};
    }}

    /* Buttons */
    QPushButton {{
        background-color: {COLOR_BG_PANEL};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        padding: 6px 14px;
        font-weight: 600;
    }}
    QPushButton:hover {{
        background-color: {COLOR_BG_HOVER};
        border-color: {COLOR_ACCENT};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_BG_SELECTED};
    }}
    QPushButton:disabled {{
        background-color: {COLOR_BG_WINDOW};
        color: {COLOR_TEXT_MUTED};
        border-color: {COLOR_BG_PANEL};
    }}

    /* Primary Accent Button */
    QPushButton#primaryButton {{
        background-color: {COLOR_ACCENT};
        color: {COLOR_BG_WINDOW};
        border: none;
    }}
    QPushButton#primaryButton:hover {{
        background-color: {COLOR_ACCENT_HOVER};
    }}

    /* Plugin List Widget */
    QListWidget {{
        background-color: {COLOR_BG_INPUT};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 4px;
        outline: none;
    }}
    QListWidget::item {{
        background-color: {COLOR_BG_PANEL};
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        margin: 3px 2px;
        padding: 2px;
    }}
    QListWidget::item:hover {{
        background-color: {COLOR_BG_HOVER};
        border-color: {COLOR_ACCENT};
    }}
    QListWidget::item:selected {{
        background-color: {COLOR_BG_SELECTED};
        border: 1px solid {COLOR_ACCENT};
    }}

    /* Detail Pane & Group Boxes */
    QFrame#detailFrame {{
        background-color: {COLOR_BG_PANEL};
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        padding: 12px;
    }}
    QFrame#diagnosticAlert {{
        background-color: #3b2328;
        border: 1px solid {COLOR_HEALTH_ERROR};
        border-radius: 6px;
        padding: 8px;
    }}

    /* Form Input Controls (SpinBox, ComboBox, CheckBox) */
    QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {COLOR_BG_INPUT};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER};
        border-radius: 6px;
        padding: 5px 10px;
        font-size: 13px;
        selection-background-color: {COLOR_ACCENT};
        selection-color: {COLOR_BG_WINDOW};
    }}
    QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border: 1px solid {COLOR_ACCENT};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 20px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLOR_BG_PANEL};
        color: {COLOR_TEXT_PRIMARY};
        border: 1px solid {COLOR_BORDER};
        selection-background-color: {COLOR_BG_SELECTED};
    }}
    QCheckBox {{
        spacing: 8px;
        color: {COLOR_TEXT_PRIMARY};
    }}
    QCheckBox::indicator {{
        width: 18px;
        height: 18px;
        border-radius: 4px;
        border: 1px solid {COLOR_BORDER};
        background-color: {COLOR_BG_INPUT};
    }}
    QCheckBox::indicator:checked {{
        background-color: {COLOR_ACCENT};
        border-color: {COLOR_ACCENT};
    }}

    /* Tab Widget & Tab Bar */
    QTabWidget::pane {{
        border: 1px solid {COLOR_BORDER};
        border-radius: 8px;
        background-color: {COLOR_BG_PANEL};
        top: -1px;
    }}
    QTabBar::tab {{
        background-color: {COLOR_BG_WINDOW};
        color: {COLOR_TEXT_MUTED};
        border: 1px solid {COLOR_BORDER};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 6px 16px;
        margin-right: 4px;
        font-weight: 600;
        font-size: 12px;
    }}
    QTabBar::tab:selected {{
        background-color: {COLOR_BG_PANEL};
        color: {COLOR_ACCENT};
        border-bottom: 1px solid {COLOR_BG_PANEL};
    }}
    QTabBar::tab:hover:!selected {{
        background-color: {COLOR_BG_HOVER};
        color: {COLOR_TEXT_PRIMARY};
    }}

    /* Scrollbars */
    QScrollBar:vertical {{
        background: {COLOR_BG_WINDOW};
        width: 8px;
        margin: 0px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {COLOR_BG_SELECTED};
        min-height: 20px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLOR_ACCENT};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Status Bar Footer */
    QLabel#footerStatus {{
        color: {COLOR_TEXT_MUTED};
        font-size: 11px;
    }}
    """
