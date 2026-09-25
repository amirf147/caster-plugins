"""
Drag Mode and Keyboard Arrow Key Nudging Interaction Handler.
Allows moving the HUD by clicking anywhere inside the window or using arrow keys.
Compatible with Python 2.7 and Python 3.x.
"""

from castervoice.lib.qt import QtCore, QtWidgets, qt_attr


class DragHandler(object):
    """
    Manages whole-window mouse dragging and keyboard pixel nudging.
    """

    def __init__(self, target_window):
        self._target = target_window
        self.is_drag_mode = False
        self._drag_pos = None

    def toggle_drag_mode(self):
        """Toggles drag mode state. Returns new state."""
        self.is_drag_mode = not self.is_drag_mode
        return self.is_drag_mode

    def set_drag_mode(self, enabled):
        self.is_drag_mode = bool(enabled)

    def handle_mouse_press(self, global_pos):
        if self.is_drag_mode:
            self._drag_pos = global_pos - self._target.frameGeometry().topLeft()
            return True
        return False

    def handle_mouse_move(self, global_pos):
        if self.is_drag_mode and self._drag_pos is not None:
            self._target.move(global_pos - self._drag_pos)
            return True
        return False

    def handle_mouse_release(self):
        self._drag_pos = None

    def nudge(self, dx, dy):
        """Nudges the window by (dx, dy) pixels."""
        self._target.move(self._target.x() + dx, self._target.y() + dy)
