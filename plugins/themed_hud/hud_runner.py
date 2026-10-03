#! python
'''
Caster HUD Window Entry Point.
Modular, reactive, themeable desktop heads-up display subsystem.
Compatible with Python 2.7 and Python 3.x.
'''
# pylint: disable=import-error,no-name-in-module
import os
import signal
import sys
import threading

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

try:
    from xmlrpc.server import SimpleXMLRPCServer
except ImportError:
    from SimpleXMLRPCServer import SimpleXMLRPCServer  # Python 2 fallback

try:  # Style C -- may be imported into Caster, or externally
    BASE_PATH = os.path.realpath(__file__).rsplit(os.path.sep + "castervoice", 1)[0]
    if BASE_PATH not in sys.path:
        sys.path.append(BASE_PATH)
finally:
    from castervoice.lib.merge.communication import Communicator
    from castervoice.lib import settings
    from castervoice.lib.qt import QtCore, QtWidgets, qapp_exec
    from hud.core import constants
    from hud.core.events import (
        RecognitionEvent,
        MicStateEvent,
        ThemeChangeEvent,
        ClearHistoryEvent,
        ActiveRulesEvent,
    )
    from hud.ipc.server import IpcServerThread
    from hud.ui.main_window import MainWindow


class SignalBridge(QtCore.QObject):
    """
    Thread-safe bridge that routes background IPC and XML-RPC requests directly into the Qt GUI thread.
    """
    event_dispatched = QtCore.Signal(object)
    show_help_requested = QtCore.Signal()
    hide_help_requested = QtCore.Signal()
    show_rules_requested = QtCore.Signal(str)
    hide_rules_requested = QtCore.Signal()
    show_hud_requested = QtCore.Signal()
    hide_hud_requested = QtCore.Signal()
    toggle_border_requested = QtCore.Signal()
    toggle_drag_requested = QtCore.Signal()
    toggle_scrollbars_requested = QtCore.Signal()
    toggle_status_bar_requested = QtCore.Signal()
    toggle_rules_bar_requested = QtCore.Signal()
    toggle_adce_requested = QtCore.Signal()
    toggle_verbose_requested = QtCore.Signal()
    font_increase_requested = QtCore.Signal()
    font_decrease_requested = QtCore.Signal()
    font_reset_requested = QtCore.Signal()
    save_profile_requested = QtCore.Signal(str)
    load_profile_requested = QtCore.Signal(str)
    show_profile_dialog_requested = QtCore.Signal(str)
    show_theme_dialog_requested = QtCore.Signal()
    set_opacity_requested = QtCore.Signal(float)
    set_background_opacity_requested = QtCore.Signal(float)
    set_text_opacity_requested = QtCore.Signal(float)
    set_text_alignment_requested = QtCore.Signal(str)
    set_theme_requested = QtCore.Signal(str)
    cycle_theme_requested = QtCore.Signal()
    clear_hud_requested = QtCore.Signal()


def handler(signum, frame):
    """Prevents unhandled exceptions on termination signal."""
    pass


def main():
    signal.signal(signal.SIGINT, handler)
    settings.initialize()
    plugin_config = {}
    if settings.SETTINGS and isinstance(settings.SETTINGS.get("plugins"), dict):
        plugin_sub = settings.SETTINGS["plugins"].get("themed_hud", {})
        if isinstance(plugin_sub, dict):
            plugin_config = plugin_sub
    legacy_config = settings.SETTINGS.get("hud", {}) if (settings.SETTINGS and isinstance(settings.SETTINGS.get("hud"), dict)) else {}
    combined_config = {**legacy_config, **plugin_config}
    merged_config = constants.merge_hud_config(combined_config)

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow(initial_config=merged_config)
    window.show()

    # Qt Signal Bridge
    bridge = SignalBridge()
    bridge.event_dispatched.connect(window.dispatch_event)
    bridge.show_help_requested.connect(window.show_help_dialog)
    bridge.hide_help_requested.connect(window.hide_help_dialog)
    bridge.show_rules_requested.connect(window.show_rules_dialog)
    bridge.hide_rules_requested.connect(window.hide_rules_dialog)
    bridge.show_hud_requested.connect(window.show_and_raise)
    bridge.hide_hud_requested.connect(window.hide)
    bridge.toggle_border_requested.connect(window.toggle_border)
    bridge.toggle_drag_requested.connect(window.toggle_drag_mode)
    bridge.toggle_scrollbars_requested.connect(window.toggle_scrollbars)
    bridge.toggle_status_bar_requested.connect(window.toggle_status_bar)
    bridge.toggle_rules_bar_requested.connect(window.toggle_active_rules_bar)
    bridge.toggle_adce_requested.connect(window.toggle_adce_bar)
    bridge.toggle_verbose_requested.connect(window.toggle_verbose_mode)
    bridge.font_increase_requested.connect(window.increase_font)
    bridge.font_decrease_requested.connect(window.decrease_font)
    bridge.font_reset_requested.connect(window.reset_font)
    bridge.save_profile_requested.connect(window.save_named_profile)
    bridge.load_profile_requested.connect(window.load_named_profile)
    bridge.show_profile_dialog_requested.connect(window.show_profile_dialog)
    bridge.show_theme_dialog_requested.connect(window.show_theme_dialog)
    bridge.set_opacity_requested.connect(window.set_opacity)
    bridge.set_background_opacity_requested.connect(window.set_background_opacity)
    bridge.set_text_opacity_requested.connect(window.set_text_opacity)
    bridge.set_text_alignment_requested.connect(window.set_text_alignment)
    bridge.set_theme_requested.connect(window.apply_theme)
    bridge.cycle_theme_requested.connect(window.cycle_theme)
    bridge.clear_hud_requested.connect(window.clear_history)

    # 1. Start Async ndjson IPC Server (High-performance telemetry stream on port 8339)
    ipc_port = int(merged_config.get("port", constants.DEFAULT_HUD_PORT))
    ipc_server = IpcServerThread(port=ipc_port, on_event=lambda ev: bridge.event_dispatched.emit(ev))
    ipc_server.start()

    # 2. Start Legacy XML-RPC Server (100% Backward Compatibility on port 8338)
    rpc_port = int(Communicator().com_registry.get("hud", constants.DEFAULT_HUD_RPC_PORT))
    rpc_server_address = (Communicator.LOCALHOST, rpc_port)
    xmlrpc_server = SimpleXMLRPCServer(rpc_server_address, logRequests=False, allow_none=True)
    _setup_xmlrpc_methods(xmlrpc_server, bridge)
    rpc_thread = threading.Thread(target=xmlrpc_server.serve_forever)
    rpc_thread.daemon = True
    rpc_thread.start()

    exit_code = qapp_exec(app)

    ipc_server.stop()
    if xmlrpc_server:
        try:
            xmlrpc_server.shutdown()
        except Exception:
            pass

    sys.exit(exit_code)


def _setup_xmlrpc_methods(server, bridge):
    """Registers legacy XML-RPC endpoints for backward-compatibility with older rule callers."""
    def _do_clear():
        bridge.clear_hud_requested.emit()
        return 0

    def _do_hide_hud():
        bridge.hide_hud_requested.emit()
        return 0

    def _do_show_hud():
        bridge.show_hud_requested.emit()
        return 0

    def _do_hide_rules():
        bridge.hide_rules_requested.emit()
        return 0

    def _do_send(text):
        bridge.event_dispatched.emit(RecognitionEvent(phrase=str(text)))
        return len(text)

    def _do_set_theme(theme):
        bridge.set_theme_requested.emit(str(theme))
        return 0

    def _do_cycle_theme():
        bridge.cycle_theme_requested.emit()
        return 0

    def _do_toggle_border():
        bridge.toggle_border_requested.emit()
        return 0

    def _do_toggle_drag():
        bridge.toggle_drag_requested.emit()
        return 0

    def _do_toggle_scrollbars():
        bridge.toggle_scrollbars_requested.emit()
        return 0

    def _do_toggle_status_bar():
        bridge.toggle_status_bar_requested.emit()
        return 0

    def _do_toggle_rules_bar():
        bridge.toggle_rules_bar_requested.emit()
        return 0

    def _do_toggle_adce():
        bridge.toggle_adce_requested.emit()
        return 0

    def _do_toggle_verbose():
        bridge.toggle_verbose_requested.emit()
        return 0

    def _do_font_increase():
        bridge.font_increase_requested.emit()
        return 0

    def _do_font_decrease():
        bridge.font_decrease_requested.emit()
        return 0

    def _do_font_reset():
        bridge.font_reset_requested.emit()
        return 0

    def _do_save_profile(name="default"):
        bridge.save_profile_requested.emit(str(name))
        return 0

    def _do_load_profile(name="default"):
        bridge.load_profile_requested.emit(str(name))
        return 0

    def _do_show_profile_dialog(mode="save"):
        bridge.show_profile_dialog_requested.emit(str(mode))
        return 0

    def _do_show_theme_dialog():
        bridge.show_theme_dialog_requested.emit()
        return 0

    def _do_set_opacity(opacity=1.0):
        bridge.set_opacity_requested.emit(float(opacity))
        return 0

    def _do_set_background_opacity(opacity=1.0):
        bridge.set_background_opacity_requested.emit(float(opacity))
        return 0

    def _do_set_text_opacity(opacity=1.0):
        bridge.set_text_opacity_requested.emit(float(opacity))
        return 0

    def _do_set_text_alignment(alignment="left"):
        bridge.set_text_alignment_requested.emit(str(alignment))
        return 0

    def _do_show_help():
        bridge.show_help_requested.emit()
        return 0

    def _do_hide_help():
        bridge.hide_help_requested.emit()
        return 0

    def _do_show_rules(json_str=""):
        bridge.show_rules_requested.emit(str(json_str))
        return len(json_str)

    def _do_kill():
        QtWidgets.QApplication.quit()
        return 0

    def _do_set_mic_mode(mode="on"):
        from hud.core.events import MicStateEvent
        bridge.event_dispatched.emit(MicStateEvent(mode=str(mode)))
        return 0

    server.register_function(_do_set_mic_mode, "set_mic_mode")
    server.register_function(_do_set_mic_mode, "set_mic_state")
    server.register_function(_do_set_mic_mode, "set_mode")
    server.register_function(_do_clear, "clear_hud")
    server.register_function(lambda: 0, "ping")
    server.register_function(_do_hide_hud, "hide_hud")
    server.register_function(_do_show_hud, "show_hud")
    server.register_function(_do_hide_rules, "hide_rules")
    server.register_function(_do_send, "send")
    server.register_function(_do_set_theme, "set_theme")
    server.register_function(_do_cycle_theme, "cycle_theme")
    server.register_function(_do_toggle_border, "toggle_border")
    server.register_function(_do_toggle_drag, "toggle_drag")
    server.register_function(_do_toggle_scrollbars, "toggle_scrollbars")
    server.register_function(_do_toggle_status_bar, "toggle_status_bar")
    server.register_function(_do_toggle_rules_bar, "toggle_rules_bar")
    server.register_function(_do_toggle_adce, "toggle_adce")
    server.register_function(_do_toggle_verbose, "toggle_verbose")
    server.register_function(_do_font_increase, "font_increase")
    server.register_function(_do_font_decrease, "font_decrease")
    server.register_function(_do_font_reset, "font_reset")
    server.register_function(_do_save_profile, "save_profile")
    server.register_function(_do_load_profile, "load_profile")
    server.register_function(_do_show_profile_dialog, "show_profile_dialog")
    server.register_function(_do_show_theme_dialog, "show_theme_dialog")
    server.register_function(_do_show_theme_dialog, "show_customizer")
    server.register_function(_do_set_opacity, "set_opacity")
    server.register_function(_do_set_background_opacity, "set_background_opacity")
    server.register_function(_do_set_text_opacity, "set_text_opacity")
    server.register_function(_do_set_text_opacity, "set_letter_opacity")
    server.register_function(_do_set_text_alignment, "set_text_alignment")
    server.register_function(_do_set_text_alignment, "set_alignment")
    server.register_function(_do_show_help, "show_help")
    server.register_function(_do_hide_help, "hide_help")
    server.register_function(_do_show_rules, "show_rules")
    server.register_function(_do_kill, "kill")


if __name__ == "__main__":
    main()
