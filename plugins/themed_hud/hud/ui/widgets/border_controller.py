"""
Dynamic Border Controller for HUD Visual Safety & Status Indications.
Implements Multi-State 2-Tone Visual Indication:
- Left/Right edges strictly display Mic Safety State (Green for Awake, Red for Sleeping).
- Top/Bottom edges display Focus (Blue) or Drag Mode (Amber) without concealing the Mic Safety State.
Compatible with Python 2.7 and Python 3.x.
"""

from castervoice.lib.qt import QtWidgets, QtGui, QtCore
from hud.core import constants


class BorderController(object):
    """
    Controls dynamic border accents on the HUD window.
    Applies zero-overhead CSS borders without changing window geometry.
    """

    def __init__(self, target_widget):
        self._target = target_widget
        self._current_border_css = None
        self._is_frameless = True
        self._enabled = True

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)

    def set_frameless(self, frameless):
        self._is_frameless = bool(frameless)

    def update_state(self, state):
        """Re-evaluates border styling from state and updates target widget if changed."""
        if not self._enabled:
            if self._current_border_css is not None:
                self._current_border_css = None
                self._apply_border("")
            return

        mic_mode_clean = str(state.mic_mode).lower().strip()
        mic_color = constants.COLOR_MIC_SLEEPING if mic_mode_clean in ("sleeping", "off") else constants.COLOR_MIC_ON
        bw = "2px" if state.theme == "high-contrast" else "1px"

        if state.is_drag_mode:
            # 2-Tone Border: Left/Right = Mic Safety State, Top/Bottom = Amber Drag Mode
            border_css = (
                "border-top: {0} solid {1}; "
                "border-bottom: {0} solid {1}; "
                "border-left: {0} solid {2}; "
                "border-right: {0} solid {2};"
            ).format(bw, constants.COLOR_DRAG, mic_color)
        elif state.is_focused:
            # 2-Tone Border: Left/Right = Mic Safety State, Top/Bottom = Blue Focus
            border_css = (
                "border-top: {0} solid {1}; "
                "border-bottom: {0} solid {1}; "
                "border-left: {0} solid {2}; "
                "border-right: {0} solid {2};"
            ).format(bw, constants.COLOR_FOCUS, mic_color)
        else:
            # Solid Border: All sides match Mic Safety State
            border_css = "border: {0} solid {1};".format(bw, mic_color)

        if border_css != self._current_border_css:
            self._current_border_css = border_css
            self._apply_border(border_css)

    def _apply_border(self, border_css):
        """Applies border CSS to the target container or viewport."""
        if hasattr(self._target, "set_border_style"):
            self._target.set_border_style(border_css)
        else:
            obj_name = self._target.objectName()
            if obj_name:
                self._target.setStyleSheet("#{0} {{ {1} }}".format(obj_name, border_css))
            else:
                self._target.setStyleSheet(border_css)
