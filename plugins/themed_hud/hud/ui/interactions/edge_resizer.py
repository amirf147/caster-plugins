"""
Cross-Platform Edge Resizer Fallback for Qt Mouse Events (Linux / macOS / Non-Win32).
"""

from castervoice.lib.qt import QtCore, QtGui, QtWidgets, qt_attr
from hud.core.constants import RESIZE_MARGIN_HORIZONTAL, RESIZE_MARGIN_VERTICAL

SIZE_ALL_CURSOR = qt_attr(QtCore, ("Qt", "SizeAllCursor"), ("Qt", "CursorShape", "SizeAllCursor"))
SIZE_HOR_CURSOR = qt_attr(QtCore, ("Qt", "SizeHorCursor"), ("Qt", "CursorShape", "SizeHorCursor"))
SIZE_VER_CURSOR = qt_attr(QtCore, ("Qt", "SizeVerCursor"), ("Qt", "CursorShape", "SizeVerCursor"))
SIZE_FDIAG_CURSOR = qt_attr(QtCore, ("Qt", "SizeFDiagCursor"), ("Qt", "CursorShape", "SizeFDiagCursor"))
SIZE_BDIAG_CURSOR = qt_attr(QtCore, ("Qt", "SizeBDiagCursor"), ("Qt", "CursorShape", "SizeBDiagCursor"))


class EdgeResizer:
    """
    Mouse-based edge detection and window resizing for frameless windows.
    """

    def __init__(self, target_window: QtWidgets.QMainWindow):
        self._target = target_window
        self.resizing_edge = None
        self.resize_start_geom = None
        self.resize_start_pos = None

    def detect_edge(self, pos: QtCore.QPoint, is_frameless: bool):
        if not is_frameless:
            return None
        w = self._target.width()
        h = self._target.height()
        x, y = pos.x(), pos.y()

        left = x <= RESIZE_MARGIN_HORIZONTAL
        right = x >= w - RESIZE_MARGIN_HORIZONTAL
        top = y <= RESIZE_MARGIN_VERTICAL
        bottom = y >= h - RESIZE_MARGIN_VERTICAL

        if top and left:
            return "top-left"
        if top and right:
            return "top-right"
        if bottom and left:
            return "bottom-left"
        if bottom and right:
            return "bottom-right"
        if left:
            return "left"
        if right:
            return "right"
        if top:
            return "top"
        if bottom:
            return "bottom"
        return None

    def update_cursor(self, edge: str, is_drag_mode: bool):
        if is_drag_mode:
            self._target.setCursor(SIZE_ALL_CURSOR)
            return
        if edge in ("top-left", "bottom-right"):
            self._target.setCursor(SIZE_FDIAG_CURSOR)
        elif edge in ("top-right", "bottom-left"):
            self._target.setCursor(SIZE_BDIAG_CURSOR)
        elif edge in ("left", "right"):
            self._target.setCursor(SIZE_HOR_CURSOR)
        elif edge in ("top", "bottom"):
            self._target.setCursor(SIZE_VER_CURSOR)
        else:
            self._target.unsetCursor()

    def handle_resize(self, global_pos: QtCore.QPoint):
        if not self.resizing_edge or not self.resize_start_geom:
            return
        dx = global_pos.x() - self.resize_start_pos.x()
        dy = global_pos.y() - self.resize_start_pos.y()
        g = self.resize_start_geom
        new_x, new_y, new_w, new_h = g.x(), g.y(), g.width(), g.height()

        if "right" in self.resizing_edge:
            new_w = max(50, g.width() + dx)
        if "bottom" in self.resizing_edge:
            new_h = max(20, g.height() + dy)
        if "left" in self.resizing_edge:
            actual_w = max(50, g.width() - dx)
            new_x = g.x() + (g.width() - actual_w)
            new_w = actual_w
        if "top" in self.resizing_edge:
            actual_h = max(20, g.height() - dy)
            new_y = g.y() + (g.height() - actual_h)
            new_h = actual_h

        self._target.setGeometry(new_x, new_y, new_w, new_h)
