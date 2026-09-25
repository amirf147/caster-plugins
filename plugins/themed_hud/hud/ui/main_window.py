"""
Caster HUD Main Composite Window.
Orchestrates reactive state reductions, UI widgets, Win32 DWM resizing, drag modes, and system tray lifecycle.
Compatible with Python 2.7 and Python 3.x.
"""

import sys
from castervoice.lib.qt import QtCore, QtGui, QtWidgets, qt_attr
from castervoice.lib import settings

from hud.core import constants
from hud.core.state import HudState
from hud.core.events import (
    HudEvent,
    MicStateEvent,
    RecognitionEvent,
    ActiveRulesEvent,
    DesktopContextEvent,
    WindowFocusEvent,
    DragModeEvent,
    ThemeChangeEvent,
    ClearHistoryEvent,
)
from hud.core.reducer import reduce_event
from hud.theming.theme_manager import ThemeManager, PRESET_THEMES
from hud.theming.profile_manager import ProfileManager

from hud.ui.widgets.border_controller import BorderController
from hud.ui.widgets.telemetry_log import TelemetryLogWidget
from hud.ui.widgets.status_bar import StatusBarWidget
from hud.ui.widgets.active_rules_bar import ActiveRulesBarWidget
from hud.ui.widgets.adce_bar import AdceBarWidget

from hud.ui.interactions.win32_frameless import Win32FramelessHelper
from hud.ui.interactions.edge_resizer import EdgeResizer
from hud.ui.interactions.drag_handler import DragHandler
from hud.ui.interactions.tray_manager import TrayManager

from hud.ui.dialogs.profile_dialog import ProfileDialog
from hud.ui.dialogs.help_dialog import HelpDialog
from hud.ui.dialogs.rules_tree_dialog import RulesTreeDialog
from hud.ui.dialogs.theme_dialog import ThemeCustomizerDialog

WINDOW_STAYS_ON_TOP_HINT = qt_attr(QtCore, ("Qt", "WindowStaysOnTopHint"), ("Qt", "WindowType", "WindowStaysOnTopHint"))
TOOL_WINDOW_HINT = qt_attr(QtCore, ("Qt", "Tool"), ("Qt", "WindowType", "Tool"))
FRAMELESS_WINDOW_HINT = qt_attr(QtCore, ("Qt", "FramelessWindowHint"), ("Qt", "WindowType", "FramelessWindowHint"))
CUSTOM_CONTEXT_MENU = qt_attr(QtCore, ("Qt", "CustomContextMenu"), ("Qt", "ContextMenuPolicy", "CustomContextMenu"))

try:
    QAction = QtGui.QAction
except AttributeError:
    QAction = QtWidgets.QAction


class MainWindow(QtWidgets.QMainWindow):
    """
    Modular, reactive Caster HUD composite window.
    """

    def __init__(self, initial_config=None):
        self.config = constants.merge_hud_config(initial_config)
        self.profile_mgr = ProfileManager()

        # Initialize State
        self.state = HudState(
            theme=ThemeManager.normalize_theme_name(self.config.get("theme", "classic")),
            frameless=bool(self.config.get("frameless", False)),
            opacity=float(self.config.get("opacity", 1.0)),
            max_history=int(self.config.get("max_history_lines", 50)),
            config=self.config,
        )

        flags = self._compute_flags()
        QtWidgets.QMainWindow.__init__(self, flags=flags)

        # Restore Geometry
        default_x = 100
        default_y = 100
        dx = int(self.config.get("width", constants.DEFAULT_HUD_WIDTH))
        dy = int(self.config.get("height", constants.DEFAULT_HUD_HEIGHT))
        x = int(self.config.get("x", default_x))
        y = int(self.config.get("y", default_y))

        # Off-screen top guard
        min_y = 0 if self.state.frameless else 30
        if y < min_y:
            y = min_y

        self.setGeometry(x, y, dx, dy)
        self.setWindowTitle(getattr(settings, "HUD_TITLE", "Caster HUD"))
        self.setMinimumSize(0, 0)
        self.setContentsMargins(0, 0, 0, 0)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(CUSTOM_CONTEXT_MENU)
        self.customContextMenuRequested.connect(self.show_context_menu)

        if self.state.opacity < 1.0:
            self.setWindowOpacity(max(0.2, min(1.0, self.state.opacity)))

        # Interaction Handlers
        self.edge_resizer = EdgeResizer(self)
        self.drag_handler = DragHandler(self)
        self._scrollbars_hidden = bool(self.config.get("hide_scrollbars", False))
        self._font_size = int(self.config.get("font_size", constants.DEFAULT_FONT_SIZE))
        self._font_family = str(self.config.get("font_family", constants.DEFAULT_FONT_FAMILY))

        # UI Components
        container = QtWidgets.QFrame(self)
        container.setObjectName("hud_container")
        container.setFrameShape(QtWidgets.QFrame.StyledPanel)
        container.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        container.setMinimumSize(0, 0)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self._container = container
        self._root_layout = QtWidgets.QVBoxLayout()
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        # 1. Optional Verbose Status Header
        self.status_bar_widget = StatusBarWidget(container)
        self.status_bar_widget.installEventFilter(self)
        self._root_layout.addWidget(self.status_bar_widget)
        if not self.config.get("show_status_bar", False):
            self.status_bar_widget.hide()

        # 2. Optional Active Rules Tag Strip
        self.active_rules_widget = ActiveRulesBarWidget(container)
        self.active_rules_widget.installEventFilter(self)
        self._root_layout.addWidget(self.active_rules_widget)
        if not self.config.get("show_active_rules", False):
            self.active_rules_widget.hide()

        # 3. Optional ADCE Dynamic Context Strip
        self.adce_widget = AdceBarWidget(container)
        self.adce_widget.installEventFilter(self)
        self._root_layout.addWidget(self.adce_widget)
        if not self.config.get("show_adce", False):
            self.adce_widget.hide()

        # 4. Telemetry Log Stream
        self.log_widget = TelemetryLogWidget(container)
        self.log_widget.viewport().installEventFilter(self)
        self.log_widget.setContextMenuPolicy(CUSTOM_CONTEXT_MENU)
        self.log_widget.customContextMenuRequested.connect(self.show_context_menu)
        self._root_layout.addWidget(self.log_widget)

        container.setLayout(self._root_layout)
        container.installEventFilter(self)
        self.setCentralWidget(container)

        # Border Controller
        self.border_controller = BorderController(self._container)
        self.border_controller.set_enabled(bool(self.config.get("status_border", True)))
        self.border_controller.set_frameless(self.state.frameless)

        # Dialogs
        self.profile_dialog = None
        self.help_dialog = None
        self.rules_dialog = None
        self.theme_dialog = None

        # System Tray Manager
        self.tray_manager = TrayManager(
            self,
            on_toggle=self.toggle_visibility,
            on_clear=self.clear_history,
            on_exit=self.close,
        )
        if self.config.get("system_tray", False):
            self.tray_manager.setup_tray()

        # Apply Stylesheet & Typography
        self.apply_theme(self.state.theme)
        if self._scrollbars_hidden:
            self.log_widget.apply_scrollbar_policy(True)
        self.log_widget.setFont(QtGui.QFont(self._font_family, self._font_size))
        self.border_controller.update_state(self.state)

    def _compute_flags(self):
        flags = WINDOW_STAYS_ON_TOP_HINT
        if self.config.get("system_tray", False):
            flags |= TOOL_WINDOW_HINT
        if self.state.frameless:
            flags |= FRAMELESS_WINDOW_HINT
        return flags

    def show_and_raise(self):
        """Shows the HUD window without stealing OS keyboard focus from active application."""
        self.showNormal()
        self.show()

    def dispatch_event(self, event):
        """
        Dispatches incoming HudEvent through pure reducer and updates observed UI slices.
        Must be executed on the Qt main GUI thread.
        """
        self.state = reduce_event(self.state, event)

        # Update Log Widget
        if isinstance(event, RecognitionEvent):
            entry = self.state.history[-1] if self.state.history else None
            if entry:
                self.log_widget.append_entry(entry, self.state.theme)
        elif isinstance(event, ClearHistoryEvent):
            self.log_widget.clear()

        # Update Optional Verbose Status Bar
        if self.status_bar_widget and self.status_bar_widget.isVisible():
            self.status_bar_widget.update_state(self.state)

        # Update Optional Active Rules Bar
        if self.active_rules_widget and (self.active_rules_widget.isVisible() or isinstance(event, (ActiveRulesEvent, MicStateEvent))):
            self.active_rules_widget.update_rules(
                self.state.voice.active_rules,
                mic_state=self.state.mic_mode
            )

        # Update Optional ADCE Dynamic Context Strip
        if self.adce_widget and (self.adce_widget.isVisible() or isinstance(event, DesktopContextEvent)):
            ctx = self.state.desktop_context
            self.adce_widget.update_context(
                process_name=ctx.process_name,
                window_title=ctx.window_title,
                semantic_zone=ctx.semantic_zone,
                active_file=ctx.active_file,
                is_connected=ctx.is_connected,
            )

        # Update Dynamic Border
        self.border_controller.update_state(self.state)

    def apply_theme(self, theme_name, background_opacity=None, text_opacity=None, text_alignment=None):
        """Applies QSS theme stylesheet preserving exact client geometry and propagates to dialogs."""
        norm_theme = ThemeManager.normalize_theme_name(theme_name)
        x, y, w, h = self.x(), self.y(), self.width(), self.height()
        theme_data = ThemeManager.get_theme_data(norm_theme)
        bg_op = background_opacity if background_opacity is not None else theme_data.get("background_opacity", self.state.background_opacity)
        txt_op = text_opacity if text_opacity is not None else theme_data.get("text_opacity", self.state.text_opacity)
        align = text_alignment if text_alignment is not None else theme_data.get("text_alignment", self.state.text_alignment)
        self.state = reduce_event(self.state, ThemeChangeEvent(theme_name=norm_theme))
        self.state = self.state.clone(
            background_opacity=float(bg_op),
            text_opacity=float(txt_op),
            text_alignment=str(align),
        )
        if hasattr(self, "log_widget"):
            self.log_widget.set_text_alignment(align)
        stylesheet = ThemeManager.get_stylesheet(norm_theme, background_opacity=bg_op, text_opacity=txt_op)
        self.setStyleSheet(stylesheet)
        self.setGeometry(x, y, w, h)

        # Propagate to dialogs
        if self.help_dialog and self.help_dialog.isVisible():
            self.help_dialog.setStyleSheet(stylesheet)
        if self.rules_dialog and self.rules_dialog.isVisible():
            self.rules_dialog.setStyleSheet(stylesheet)
        if self.profile_dialog and self.profile_dialog.isVisible():
            self.profile_dialog.setStyleSheet(stylesheet)
        if self.theme_dialog and self.theme_dialog.isVisible():
            self.theme_dialog.setStyleSheet(stylesheet)

        # Re-render history entries with new theme colors
        if self.state.history:
            self.log_widget.update_history(self.state.history, norm_theme)

        self.border_controller.update_state(self.state)

    def cycle_theme(self):
        """Cycles through built-in theme presets."""
        themes = ThemeManager.get_available_themes()
        curr = ThemeManager.normalize_theme_name(self.state.theme)
        idx = themes.index(curr) if curr in themes else 0
        next_theme = themes[(idx + 1) % len(themes)]
        self.apply_theme(next_theme)
        self.log_widget.append_system_text("Theme: {0}".format(next_theme), self.state.theme)

    def toggle_border(self):
        """Toggles between framed (title bar) and frameless overlay while preserving focus."""
        new_frameless = not self.state.frameless
        self.state = self.state.clone(frameless=new_frameless)
        self.border_controller.set_frameless(new_frameless)

        client_pos = self.mapToGlobal(QtCore.QPoint(0, 0))
        w, h = self.width(), self.height()

        self.setWindowFlags(self._compute_flags())
        self.setGeometry(client_pos.x(), client_pos.y(), w, h)
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self.log_widget.setFocus()
        self.border_controller.update_state(self.state)
        self.log_widget.append_system_text("HUD: {0}".format('Frameless' if new_frameless else 'Title Bar'), self.state.theme)

    def toggle_drag_mode(self):
        """Toggles mouse & arrow key drag mode."""
        is_drag = self.drag_handler.toggle_drag_mode()
        self.dispatch_event(DragModeEvent(is_drag_mode=is_drag))
        msg = "Drag Mode: Enabled (Click & Drag or Arrow Keys to move, 'D' to lock)" if is_drag else "Drag Mode: Locked"
        self.log_widget.append_system_text(msg, self.state.theme)

    def toggle_scrollbars(self):
        """Toggles scrollbars on/off."""
        self._scrollbars_hidden = not self._scrollbars_hidden
        self.log_widget.apply_scrollbar_policy(self._scrollbars_hidden)
        msg = "HUD: Scrollbars Hidden" if self._scrollbars_hidden else "HUD: Scrollbars Visible"
        self.log_widget.append_system_text(msg, self.state.theme)

    def toggle_status_bar(self):
        """Toggles top header status bar on/off."""
        if self.status_bar_widget.isVisible():
            self.status_bar_widget.hide()
            msg = "HUD: Status Header Hidden"
        else:
            self.status_bar_widget.update_state(self.state)
            self.status_bar_widget.show()
            msg = "HUD: Status Header Visible"
        self.log_widget.append_system_text(msg, self.state.theme)

    def toggle_active_rules_bar(self):
        """Toggles active rules tag strip on/off."""
        if self.active_rules_widget.isVisible():
            self.active_rules_widget.hide()
            msg = "HUD: Active Rules Strip Hidden"
        else:
            self.active_rules_widget.update_rules(
                self.state.voice.active_rules,
                mic_state=self.state.mic_mode
            )
            self.active_rules_widget.show()
            msg = "HUD: Active Rules Strip Visible"
        self.log_widget.append_system_text(msg, self.state.theme)

    def toggle_adce_bar(self):
        """Toggles ADCE dynamic context strip on/off."""
        if self.adce_widget.isVisible():
            self.adce_widget.hide()
            msg = "HUD: ADCE Context Strip Hidden"
        else:
            ctx = self.state.desktop_context
            self.adce_widget.update_context(
                process_name=ctx.process_name,
                window_title=ctx.window_title,
                semantic_zone=ctx.semantic_zone,
                active_file=ctx.active_file,
                is_connected=ctx.is_connected,
            )
            self.adce_widget.show()
            msg = "HUD: ADCE Context Strip Visible"
        self.log_widget.append_system_text(msg, self.state.theme)

    def toggle_verbose_mode(self):
        """
        Toggles verbose diagnostic panels (Status Header + Active Rules Strip).
        Note: ADCE Dynamic Context Strip is managed independently and is not toggled by verbose mode.
        """
        if self.status_bar_widget.isVisible() or self.active_rules_widget.isVisible():
            self.status_bar_widget.hide()
            self.active_rules_widget.hide()
            msg = "HUD: Verbose Mode Off"
        else:
            self.status_bar_widget.update_state(self.state)
            self.status_bar_widget.show()
            self.active_rules_widget.update_rules(self.state.voice.active_rules)
            self.active_rules_widget.show()
            msg = "HUD: Verbose Mode On"
        self.log_widget.append_system_text(msg, self.state.theme)

    def increase_font(self):
        self._font_size = min(36, self._font_size + 1)
        self.log_widget.setFont(QtGui.QFont(self._font_family, self._font_size))
        self.log_widget.append_system_text("Font Size: {0}pt".format(self._font_size), self.state.theme)

    def decrease_font(self):
        self._font_size = max(6, self._font_size - 1)
        self.log_widget.setFont(QtGui.QFont(self._font_family, self._font_size))
        self.log_widget.append_system_text("Font Size: {0}pt".format(self._font_size), self.state.theme)

    def reset_font(self):
        self._font_size = constants.DEFAULT_FONT_SIZE
        self.log_widget.setFont(QtGui.QFont(self._font_family, self._font_size))
        self.log_widget.append_system_text("Font Size Reset ({0}pt)".format(self._font_size), self.state.theme)

    def clear_history(self):
        self.dispatch_event(ClearHistoryEvent())

    def toggle_visibility(self):
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.show_and_raise()

    def set_opacity(self, opacity):
        """Sets the HUD window opacity between 0.1 and 1.0."""
        val = max(0.1, min(1.0, float(opacity)))
        self.state = self.state.clone(opacity=val)
        self.setWindowOpacity(val)

    def set_background_opacity(self, opacity):
        """Sets the HUD background opacity between 0.0 and 1.0."""
        val = max(0.0, min(1.0, float(opacity)))
        self.state = self.state.clone(background_opacity=val)
        stylesheet = ThemeManager.get_stylesheet(
            self.state.theme,
            background_opacity=val,
            text_opacity=self.state.text_opacity,
        )
        self.setStyleSheet(stylesheet)

    def set_text_opacity(self, opacity):
        """Sets the HUD letters/text opacity between 0.1 and 1.0."""
        val = max(0.1, min(1.0, float(opacity)))
        self.state = self.state.clone(text_opacity=val)
        stylesheet = ThemeManager.get_stylesheet(
            self.state.theme,
            background_opacity=self.state.background_opacity,
            text_opacity=val,
        )
        self.setStyleSheet(stylesheet)
        if self.state.history:
            self.log_widget.update_history(self.state.history, self.state.theme)

    def set_text_alignment(self, alignment):
        """Sets the HUD text alignment to 'left' or 'right'."""
        val = "right" if str(alignment).lower() == "right" else "left"
        self.state = self.state.clone(text_alignment=val)
        if hasattr(self, "log_widget"):
            self.log_widget.set_text_alignment(val)

    def show_theme_dialog(self):
        """Opens the interactive Theme Customizer and appearance settings dialog."""
        if self.theme_dialog is None:
            self.theme_dialog = ThemeCustomizerDialog(
                self,
                theme_name=self.state.theme,
                use_tray=self.config.get("system_tray", False),
            )
        else:
            self.theme_dialog.refresh_state(
                self.state.theme,
                background_opacity=self.state.background_opacity,
                text_opacity=self.state.text_opacity,
                text_alignment=self.state.text_alignment,
            )
            self.theme_dialog.setStyleSheet(ThemeManager.get_stylesheet(self.state.theme))
        self.theme_dialog.show_dialog()

    def show_profile_dialog(self, mode="save"):
        if self.profile_dialog is None:
            self.profile_dialog = ProfileDialog(self, self.profile_mgr, theme_name=self.state.theme,
                                                use_tray=self.config.get("system_tray", False))
        else:
            self.profile_dialog.setStyleSheet(ThemeManager.get_stylesheet(self.state.theme))
        self.profile_dialog.show_dialog(mode=mode)

    def show_help_dialog(self):
        if self.help_dialog is None:
            self.help_dialog = HelpDialog(theme_name=self.state.theme, use_tray=self.config.get("system_tray", False))
        else:
            self.help_dialog.setStyleSheet(ThemeManager.get_stylesheet(self.state.theme))
        self.help_dialog.show()
        self.help_dialog.raise_()
        self.help_dialog.activateWindow()

    def hide_help_dialog(self):
        if self.help_dialog:
            self.help_dialog.close()

    def show_rules_dialog(self, json_text=""):
        if not json_text:
            try:
                from castervoice.asynch import hud_support
                hud_support.show_rules()
                return
            except Exception:
                json_text = "[]"
        if self.rules_dialog:
            self.rules_dialog.close()
        self.rules_dialog = RulesTreeDialog(json_text, theme_name=self.state.theme,
                                            use_tray=self.config.get("system_tray", False))
        self.rules_dialog.show()
        self.rules_dialog.raise_()
        self.rules_dialog.activateWindow()

    def hide_rules_dialog(self):
        if self.rules_dialog:
            self.rules_dialog.close()
            self.rules_dialog = None

    def save_named_profile(self, name="default"):
        profile_data = {
            "x": self.x(),
            "y": self.y(),
            "width": self.width(),
            "height": self.height(),
            "theme": self.state.theme,
            "frameless": self.state.frameless,
            "opacity": self.state.opacity,
            "background_opacity": self.state.background_opacity,
            "text_opacity": self.state.text_opacity,
            "text_alignment": self.state.text_alignment,
        }
        self.profile_mgr.save_profile(name, profile_data)
        self.log_widget.append_system_text("Profile Saved: '{0}'".format(name), self.state.theme)

    def load_named_profile(self, name="default"):
        data = self.profile_mgr.load_profile(name)
        if not data:
            self.log_widget.append_system_text("Profile '{0}' not found".format(name), self.state.theme)
            return

        x = data.get("x", self.x())
        y = data.get("y", self.y())
        w = data.get("width", self.width())
        h = data.get("height", self.height())

        if "theme" in data:
            self.apply_theme(data["theme"])
        if "opacity" in data:
            self.set_opacity(data["opacity"])
        if "background_opacity" in data:
            self.set_background_opacity(data["background_opacity"])
        if "text_opacity" in data:
            self.set_text_opacity(data["text_opacity"])
        if "text_alignment" in data:
            self.set_text_alignment(data["text_alignment"])
        if "frameless" in data and data["frameless"] != self.state.frameless:
            self.state = self.state.clone(frameless=data["frameless"])
            self.border_controller.set_frameless(data["frameless"])
            self.setWindowFlags(self._compute_flags())

        self.setGeometry(x, y, w, h)
        self.show()
        self.log_widget.append_system_text("Profile Loaded: '{0}'".format(name), self.state.theme)

    def reset_to_default_profile(self):
        self.setGeometry(100, 100, constants.DEFAULT_HUD_WIDTH, constants.DEFAULT_HUD_HEIGHT)
        self.apply_theme(constants.DEFAULT_HUD_CONFIG["theme"])
        self.set_text_alignment("left")
        self.log_widget.append_system_text("Default Profile Reset", self.state.theme)

    def show_context_menu(self, pos):
        """Build and display the complete HUD right-click context menu."""
        menu = QtWidgets.QMenu(self)

        rules_act = QAction("Show Active Rules", self)
        rules_act.triggered.connect(lambda: self.show_rules_dialog(""))
        menu.addAction(rules_act)

        help_act = QAction("Help / Voice Commands", self)
        help_act.triggered.connect(self.show_help_dialog)
        menu.addAction(help_act)

        menu.addSeparator()

        border_act = QAction("Toggle Border [T]", self)
        border_act.triggered.connect(self.toggle_border)
        menu.addAction(border_act)

        drag_text = "Lock Drag Mode [D]" if self.drag_handler.is_drag_mode else "Enable Drag Mode [D]"
        drag_act = QAction(drag_text, self)
        drag_act.triggered.connect(self.toggle_drag_mode)
        menu.addAction(drag_act)

        # Panels / Widgets Submenu
        panel_menu = menu.addMenu("Panels / Widgets")
        verbose_act = QAction("Toggle Verbose Mode", self)
        verbose_act.triggered.connect(self.toggle_verbose_mode)
        panel_menu.addAction(verbose_act)

        status_act = QAction("Toggle Header Status Bar", self)
        status_act.triggered.connect(self.toggle_status_bar)
        panel_menu.addAction(status_act)

        rules_bar_act = QAction("Toggle Active Rules Strip", self)
        rules_bar_act.triggered.connect(self.toggle_active_rules_bar)
        panel_menu.addAction(rules_bar_act)

        adce_bar_act = QAction("Toggle ADCE Context Strip", self)
        adce_bar_act.triggered.connect(self.toggle_adce_bar)
        panel_menu.addAction(adce_bar_act)

        scroll_text = "Hide Scrollbars" if not self._scrollbars_hidden else "Show Scrollbars"
        scroll_act = QAction(scroll_text, self)
        scroll_act.triggered.connect(self.toggle_scrollbars)
        panel_menu.addAction(scroll_act)

        # Customize / Themes
        theme_act = QAction("Customize / Themes...", self)
        theme_act.triggered.connect(self.show_theme_dialog)
        menu.addAction(theme_act)

        # Text Alignment Submenu
        align_menu = menu.addMenu("Text Alignment")
        left_act = QAction("Left Aligned", self)
        left_act.setCheckable(True)
        left_act.setChecked(self.state.text_alignment == "left")
        left_act.triggered.connect(lambda: self.set_text_alignment("left"))
        align_menu.addAction(left_act)

        right_act = QAction("Right Aligned", self)
        right_act.setCheckable(True)
        right_act.setChecked(self.state.text_alignment == "right")
        right_act.triggered.connect(lambda: self.set_text_alignment("right"))
        align_menu.addAction(right_act)

        # Profiles Submenu
        profile_menu = menu.addMenu("Profiles")
        save_prof_act = QAction("Save Profile [Enter]", self)
        save_prof_act.triggered.connect(lambda: self.show_profile_dialog("save"))
        profile_menu.addAction(save_prof_act)

        load_prof_act = QAction("Load Profile [L]", self)
        load_prof_act.triggered.connect(lambda: self.show_profile_dialog("load"))
        profile_menu.addAction(load_prof_act)

        reset_prof_act = QAction("Reset to Default [R]", self)
        reset_prof_act.triggered.connect(self.reset_to_default_profile)
        profile_menu.addAction(reset_prof_act)

        menu.addSeparator()

        clear_act = QAction("Clear Output", self)
        clear_act.triggered.connect(self.clear_history)
        menu.addAction(clear_act)

        if self.config.get("system_tray", False):
            hide_act = QAction("Hide to Tray", self)
            hide_act.triggered.connect(self.hide)
            menu.addAction(hide_act)

        exit_act = QAction("Exit", self)
        exit_act.triggered.connect(self.close)
        menu.addAction(exit_act)

        if isinstance(pos, QtCore.QPoint):
            global_pos = self.mapToGlobal(pos)
        else:
            global_pos = QtGui.QCursor.pos()
        menu.exec_(global_pos)

    def contextMenuEvent(self, event):
        """Native context menu event handler."""
        self.show_context_menu(event.pos())
        event.accept()

    def handle_key(self, event):
        """Processes keyboard hotkeys for HUD navigation and nudging."""
        key_t = qt_attr(QtCore, ("Qt", "Key_T"), ("Qt", "Key", "Key_T"))
        key_d = qt_attr(QtCore, ("Qt", "Key_D"), ("Qt", "Key", "Key_D"))
        key_esc = qt_attr(QtCore, ("Qt", "Key_Escape"), ("Qt", "Key", "Key_Escape"))
        key_left = qt_attr(QtCore, ("Qt", "Key_Left"), ("Qt", "Key", "Key_Left"))
        key_right = qt_attr(QtCore, ("Qt", "Key_Right"), ("Qt", "Key", "Key_Right"))
        key_up = qt_attr(QtCore, ("Qt", "Key_Up"), ("Qt", "Key", "Key_Up"))
        key_down = qt_attr(QtCore, ("Qt", "Key_Down"), ("Qt", "Key", "Key_Down"))

        shift_mod = qt_attr(QtCore, ("Qt", "ShiftModifier"), ("Qt", "KeyboardModifier", "ShiftModifier"))
        shift = bool(event.modifiers() & shift_mod)
        step = 10 if shift else 1

        if event.key() == key_t:
            self.toggle_border()
            return True

        if event.key() == key_d:
            self.toggle_drag_mode()
            return True

        if event.key() == key_esc and self.drag_handler.is_drag_mode:
            self.toggle_drag_mode()
            return True

        if self.drag_handler.is_drag_mode:
            if event.key() == key_left:
                self.drag_handler.nudge(-step, 0)
                return True
            if event.key() == key_right:
                self.drag_handler.nudge(step, 0)
                return True
            if event.key() == key_up:
                self.drag_handler.nudge(0, -step)
                return True
            if event.key() == key_down:
                self.drag_handler.nudge(0, step)
                return True

        return False

    def nativeEvent(self, event_type, message):
        """Native Win32 WM_NCHITTEST handler for DWM hardware border resizing."""
        if self.state.frameless:
            handled, result = Win32FramelessHelper.handle_native_event(self, event_type, message)
            if handled:
                return True, result
        return QtWidgets.QMainWindow.nativeEvent(self, event_type, message)

    def eventFilter(self, obj, event):
        """Viewport and header event filter capturing direct mouse drag and edge resizing."""
        left_btn = qt_attr(QtCore, ("Qt", "LeftButton"), ("Qt", "MouseButton", "LeftButton"))

        # 1. Direct Mouse Dragging from Header Strips (Status Bar, Active Rules, ADCE, Container)
        is_header = obj in (getattr(self, "status_bar_widget", None),
                            getattr(self, "active_rules_widget", None),
                            getattr(self, "adce_widget", None),
                            getattr(self, "_container", None))
        if not is_header and hasattr(obj, "parent"):
            p = obj.parent()
            if p in (getattr(self, "status_bar_widget", None),
                     getattr(self, "active_rules_widget", None),
                     getattr(self, "adce_widget", None)):
                is_header = True

        if is_header:
            if event.type() == QtCore.QEvent.MouseButtonPress and event.button() == left_btn:
                self._header_drag_pos = event.globalPos() - self.frameGeometry().topLeft()
                return True
            elif event.type() == QtCore.QEvent.MouseMove and event.buttons() == left_btn and getattr(self, "_header_drag_pos", None) is not None:
                self.move(event.globalPos() - self._header_drag_pos)
                return True
            elif event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == left_btn:
                self._header_drag_pos = None
                return True
            elif event.type() == QtCore.QEvent.ContextMenu:
                self.show_context_menu(event.pos())
                return True

        # 2. Main Log Widget Viewport (Drag Mode / Edge Resizing)
        log_w = getattr(self, "log_widget", None)
        if log_w and obj == log_w.viewport():
            if event.type() == QtCore.QEvent.MouseMove:
                global_pos = event.globalPos()
                if self.drag_handler.handle_mouse_move(global_pos):
                    return True
                if self.edge_resizer.resizing_edge and event.buttons() == left_btn:
                    self.edge_resizer.handle_resize(global_pos)
                    return True
                edge = self.edge_resizer.detect_edge(self.mapFromGlobal(global_pos), self.state.frameless)
                self.edge_resizer.update_cursor(edge, self.drag_handler.is_drag_mode)

            elif event.type() == QtCore.QEvent.MouseButtonPress and event.button() == left_btn:
                global_pos = event.globalPos()
                edge = self.edge_resizer.detect_edge(self.mapFromGlobal(global_pos), self.state.frameless)
                if edge and not sys.platform == "win32":
                    self.edge_resizer.resizing_edge = edge
                    self.edge_resizer.resize_start_geom = self.geometry()
                    self.edge_resizer.resize_start_pos = global_pos
                    return True
                if self.drag_handler.handle_mouse_press(global_pos):
                    return True

            elif event.type() == QtCore.QEvent.MouseButtonRelease and event.button() == left_btn:
                self.edge_resizer.resizing_edge = None
                self.drag_handler.handle_mouse_release()

        return QtWidgets.QMainWindow.eventFilter(self, obj, event)

    def keyPressEvent(self, event):
        if self.handle_key(event):
            event.accept()
            return
        QtWidgets.QMainWindow.keyPressEvent(self, event)

    def changeEvent(self, event):
        if event.type() == QtCore.QEvent.ActivationChange:
            is_focused = self.isActiveWindow()
            self.dispatch_event(WindowFocusEvent(is_focused=is_focused))
        QtWidgets.QMainWindow.changeEvent(self, event)

    def showEvent(self, event):
        self.tray_manager.update_visibility_text(True)
        QtWidgets.QMainWindow.showEvent(self, event)

    def hideEvent(self, event):
        self.tray_manager.update_visibility_text(False)
        QtWidgets.QMainWindow.hideEvent(self, event)

    def closeEvent(self, event):
        self.tray_manager.hide_tray()
        QtWidgets.QApplication.quit()
        event.accept()
