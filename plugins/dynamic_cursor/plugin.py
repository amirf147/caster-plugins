# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Dynamic Cursor Plugin for Caster.

Integrates Caster microphone telemetry and Active Desktop Context Engine (ADCE)
semantic focus zones with the native Windows hardware cursor via Named Pipe IPC.
"""

import logging
import os
import shutil
import subprocess
import sys
from typing import Optional

try:
    from castervoice.lib import printer
except ImportError:
    printer = None

try:
    from castervoice.lib.plugin import PluginBase
except ImportError:
    try:
        from plugins.common.plugin_base import PluginBase
    except ImportError:
        try:
            from ..common.plugin_base import PluginBase
        except ImportError:
            class PluginBase:
                def __init__(self):
                    self._nexus = None
                    self._config = None
                    self.is_running = False

                def initialize(self, nexus, config):
                    self._nexus = nexus
                    self._config = config

                def start(self):
                    self.is_running = True

                def stop(self):
                    self.is_running = False

try:
    from plugins.common.desktop_context import DesktopContextProvider
except ImportError:
    try:
        from ..common.desktop_context import DesktopContextProvider
    except ImportError:
        DesktopContextProvider = None

from .bridge import DynamicCursorBridgeClient
from .context_mapper import resolve_context_badge
from .printer_handler import DynamicCursorPrintHandler

_logger = logging.getLogger("caster.plugins.dynamic_cursor")


def _find_daemon_executable() -> Optional[str]:
    """Locates the Dynamic Cursor daemon executable across paths."""
    env_exe = os.environ.get("DYNAMIC_CURSOR_EXE")
    if env_exe and os.path.isfile(env_exe):
        return env_exe

    repo_candidates = [
        os.path.expanduser("~/Documents/repos/dynamic-cursor/build/dynamic-cursor-tray.exe"),
        os.path.expanduser("~/Documents/repos/dynamic-cursor/build/Release/dynamic-cursor-tray.exe"),
        os.path.expanduser("~/Documents/repos/dynamic-cursor/build/bin/dynamic-cursor-tray.exe"),
        os.path.expanduser("~/Documents/repos/dynamic-cursor/dynamic-cursor-tray.exe"),
    ]
    for candidate in repo_candidates:
        if os.path.isfile(candidate):
            return candidate

    which_tray = shutil.which("dynamic-cursor-tray.exe") or shutil.which("dynamic-cursor-tray")
    if which_tray:
        return which_tray

    return None


def _launch_daemon_detached(exe_path: str) -> None:
    """Spawns the Dynamic Cursor daemon as a detached background process."""
    creationflags = 0
    if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP"):
        creationflags |= subprocess.CREATE_NEW_PROCESS_GROUP
    if hasattr(subprocess, "DETACHED_PROCESS"):
        creationflags |= subprocess.DETACHED_PROCESS

    try:
        subprocess.Popen(
            [exe_path],
            creationflags=creationflags,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _logger.info("Spawned Dynamic Cursor daemon: %s", exe_path)
    except Exception as ex:
        _logger.debug("Failed to spawn Dynamic Cursor daemon: %s", ex)


class DynamicCursorPlugin(PluginBase):
    """
    Caster plugin projecting microphone states and ADCE focus badges to Windows cursor.
    """

    name = "dynamic_cursor"
    version = "1.0.0"
    description = (
        "Event-driven Dynamic Cursor bridge projecting Caster mic states and "
        "ADCE semantic focus badges onto the Windows hardware cursor."
    )

    def __init__(self):
        super(DynamicCursorPlugin, self).__init__()
        self._bridge = None
        self._print_handler = None
        self._adce_connected = False
        self._running = False

    def initialize(self, nexus, config):
        """Initializes plugin configuration, bridge client, and event subscriptions."""
        super(DynamicCursorPlugin, self).initialize(nexus, config)
        if sys.platform != "win32":
            _logger.warning("dynamic_cursor plugin is only supported on Windows. Skipping initialization.")
            return

        cfg = config or {}
        pipe_name = str(cfg.get("pipe_name", "dynamic_cursor"))
        autostart_daemon = bool(cfg.get("autostart_daemon", True))
        enable_mic_tint = bool(cfg.get("enable_mic_tint", True))
        enable_context_badges = bool(cfg.get("enable_context_badges", True))
        listening_tint = str(cfg.get("listening_tint", "#44FF66"))
        sleeping_tint = str(cfg.get("sleeping_tint", "#FF5555"))
        muted_tint = str(cfg.get("muted_tint", "#888888"))

        pipe_path = f"\\\\.\\pipe\\{pipe_name}"
        if autostart_daemon and not os.path.exists(pipe_path):
            exe_path = _find_daemon_executable()
            if exe_path:
                _launch_daemon_detached(exe_path)

        self._bridge = DynamicCursorBridgeClient.get_instance(
            pipe_name=pipe_name,
            enable_mic_tint=enable_mic_tint,
            enable_context_badges=enable_context_badges,
            listening_tint=listening_tint,
            sleeping_tint=sleeping_tint,
            muted_tint=muted_tint,
        )

        self._print_handler = DynamicCursorPrintHandler(bridge=self._bridge)
        if printer and hasattr(printer, "get_delegating_handler"):
            dh = printer.get_delegating_handler()
            if hasattr(dh, "register_handler"):
                dh.register_handler(self._print_handler)

        if nexus and hasattr(nexus, "engine_modes_manager") and nexus.engine_modes_manager:
            nexus.engine_modes_manager.add_mic_listener(self._on_mic_mode_changed)

        try:
            from adce import add_context_listener
            add_context_listener(self._on_adce_context_changed)
        except Exception:
            try:
                from caster_user_content.plugins.adce import add_context_listener
                add_context_listener(self._on_adce_context_changed)
            except Exception:
                pass

    def _on_mic_mode_changed(self, mode: str):
        """Dispatches microphone state updates to the Dynamic Cursor bridge."""
        if not self._bridge:
            return
        self._bridge.update_mic_layer(mode)

    def _on_adce_context_changed(
        self,
        process_name: str = "",
        window_title: str = "",
        semantic_zone: str = "",
        active_file: str = "",
        is_connected: bool = True,
        **kwargs,
    ):
        """Dispatches ADCE context updates to the Dynamic Cursor bridge."""
        self._adce_connected = bool(is_connected)
        if not self._bridge:
            return

        if is_connected:
            badge_id = resolve_context_badge(process_name, semantic_zone, window_title)
            self._bridge.update_context_layer(badge_id)
        else:
            badge_id = resolve_context_badge(process_name, "", window_title)
            self._bridge.update_context_layer(badge_id)

    def _on_desktop_context_changed(self, snapshot):
        """Handles context updates from DesktopContextProvider."""
        if not self._bridge or not self._running:
            return

        zone = snapshot.semantic_zone if snapshot.is_adce_connected else ""
        badge_id = resolve_context_badge(
            snapshot.process_name,
            zone,
            snapshot.window_title,
        )
        self._bridge.update_context_layer(badge_id)

    def start(self):
        """Starts bridge client and subscribes to DesktopContextProvider."""
        super(DynamicCursorPlugin, self).start()
        if sys.platform != "win32":
            return
        self._running = True

        if self._bridge:
            self._bridge.start()

            current_mic = "on"
            if self._nexus and hasattr(self._nexus, "engine_modes_manager") and self._nexus.engine_modes_manager:
                current_mic = self._nexus.engine_modes_manager.get_mic_mode() or "on"
            self._bridge.update_mic_layer(current_mic)

        if DesktopContextProvider:
            DesktopContextProvider.get_instance().add_listener(self._on_desktop_context_changed)

    def stop(self):
        """Performs clean teardown of bridge client and listener subscriptions."""
        super(DynamicCursorPlugin, self).stop()
        self._running = False

        if DesktopContextProvider:
            DesktopContextProvider.get_instance().remove_listener(self._on_desktop_context_changed)

        if self._bridge:
            self._bridge.stop()

        if self._print_handler and printer and hasattr(printer, "get_delegating_handler"):
            dh = printer.get_delegating_handler()
            if hasattr(dh, "unregister_handler"):
                dh.unregister_handler(self._print_handler)
            elif hasattr(dh, "_handlers"):
                try:
                    if self._print_handler in dh._handlers:
                        dh._handlers.remove(self._print_handler)
                except Exception:
                    pass
            self._print_handler = None

        if self._nexus and hasattr(self._nexus, "engine_modes_manager") and self._nexus.engine_modes_manager:
            try:
                self._nexus.engine_modes_manager.remove_mic_listener(self._on_mic_mode_changed)
            except Exception:
                pass

        try:
            from adce import remove_context_listener
            remove_context_listener(self._on_adce_context_changed)
        except Exception:
            try:
                from caster_user_content.plugins.adce import remove_context_listener
                remove_context_listener(self._on_adce_context_changed)
            except Exception:
                pass


def get_plugin() -> DynamicCursorPlugin:
    """Entry point returning a new DynamicCursorPlugin instance."""
    return DynamicCursorPlugin()
