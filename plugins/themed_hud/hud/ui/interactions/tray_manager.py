"""
System Tray Manager for Caster HUD.
Provides notification area docking, dynamic 2D vector badge icon, and mouse context menu.
"""

from typing import Callable, Optional
from castervoice.lib.qt import QtCore, QtGui, QtWidgets, qt_attr
from castervoice.lib import settings

QSystemTrayIcon = getattr(QtWidgets, "QSystemTrayIcon", None)
QMenu = getattr(QtWidgets, "QMenu", None)
QStyle = QtWidgets.QStyle
try:
    QAction = QtGui.QAction
except AttributeError:
    QAction = QtWidgets.QAction


def create_hud_icon(app: Optional[QtWidgets.QApplication] = None) -> QtGui.QIcon:
    """Create a crisp 2D vector badge icon for the system tray."""
    try:
        pixmap = QtGui.QPixmap(32, 32)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.setBrush(QtGui.QColor(41, 128, 185))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(2, 2, 28, 28, 6, 6)
        painter.setPen(QtGui.QColor(255, 255, 255))
        font = QtGui.QFont("Arial", 14, QtGui.QFont.Bold)
        painter.setFont(font)
        painter.drawText(QtCore.QRect(0, 0, 32, 32), QtCore.Qt.AlignCenter, "C")
        painter.end()
        return QtGui.QIcon(pixmap)
    except Exception:
        if app is not None:
            return app.style().standardIcon(QStyle.SP_DesktopIcon)
        return QtGui.QIcon()


class TrayManager:
    """
    Manages QSystemTrayIcon and context menu.
    """

    def __init__(self, main_window: QtWidgets.QMainWindow, on_toggle: Callable[[], None],
                 on_clear: Callable[[], None], on_exit: Callable[[], None]):
        self._target = main_window
        self._on_toggle = on_toggle
        self._on_clear = on_clear
        self._on_exit = on_exit
        self.tray_icon: Optional[QtWidgets.QSystemTrayIcon] = None
        self.toggle_action = None

    def setup_tray(self):
        if QSystemTrayIcon is None or not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self._target)
        app = QtWidgets.QApplication.instance()
        icon = create_hud_icon(app)
        self.tray_icon.setIcon(icon)
        self.tray_icon.setToolTip(settings.HUD_TITLE)

        if QMenu is not None:
            tray_menu = QMenu(self._target)
            self.toggle_action = QAction("Hide HUD", self._target)
            self.toggle_action.triggered.connect(self._on_toggle)
            tray_menu.addAction(self.toggle_action)

            clear_action = QAction("Clear HUD", self._target)
            clear_action.triggered.connect(self._on_clear)
            tray_menu.addAction(clear_action)

            tray_menu.addSeparator()

            exit_action = QAction("Exit", self._target)
            exit_action.triggered.connect(self._on_exit)
            tray_menu.addAction(exit_action)

            self.tray_icon.setContextMenu(tray_menu)

        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def update_visibility_text(self, is_visible: bool):
        if self.toggle_action:
            self.toggle_action.setText("Hide HUD" if is_visible else "Show HUD")

    def hide_tray(self):
        if self.tray_icon:
            self.tray_icon.hide()

    def _on_tray_activated(self, reason):
        trigger_val = qt_attr(
            QtWidgets,
            ("QSystemTrayIcon", "Trigger"),
            ("QSystemTrayIcon", "ActivationReason", "Trigger"),
        )
        double_click_val = qt_attr(
            QtWidgets,
            ("QSystemTrayIcon", "DoubleClick"),
            ("QSystemTrayIcon", "ActivationReason", "DoubleClick"),
        )
        if reason in (trigger_val, double_click_val):
            self._on_toggle()
