# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Taskbar HUD Plugin

Integrates Caster voice recognition and mic telemetry with the Windows 11
Taskbar HUD Windhawk mod via Named Pipe.
"""

import ctypes
from ctypes import wintypes
import logging
import os
import sys
import threading
import time

from castervoice.lib import printer
from castervoice.lib.plugin import PluginBase
from .bridge import TaskbarHudBridgeClient
from .printer_handler import TaskbarHudPrintHandler
from .context_resolver import resolve_active_rules

_logger = logging.getLogger("caster.plugins.taskbar_hud")

if sys.platform == "win32":
    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
else:
    _user32 = None
    _kernel32 = None

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def _get_foreground_window_info():
    """Returns (process_name, window_title) for active foreground window via native Win32."""
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return "", ""

        # Window Title
        length = _user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value

        # Process Name
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return "", title

        h_proc = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        proc_name = ""
        if h_proc:
            try:
                size = wintypes.DWORD(1024)
                name_buf = ctypes.create_unicode_buffer(1024)
                if _kernel32.QueryFullProcessImageNameW(h_proc, 0, name_buf, ctypes.byref(size)):
                    proc_name = os.path.basename(name_buf.value)
                    if proc_name.lower().endswith(".exe"):
                        proc_name = proc_name[:-4]
            finally:
                _kernel32.CloseHandle(h_proc)

        return proc_name, title
    except Exception as ex:
        _logger.debug("Error querying foreground window info: %s", ex)
        return "", ""


class TaskbarHudPlugin(PluginBase):
    name = "taskbar_hud"
    version = "1.0.0"
    description = "Windows 11 Taskbar HUD Windhawk Mod Bridge"

    def __init__(self):
        super(TaskbarHudPlugin, self).__init__()
        self._bridge = None
        self._print_handler = None
        self._adce_connected = False
        self._running = False
        self._watcher_thread = None

    def initialize(self, nexus, config):
        super(TaskbarHudPlugin, self).initialize(nexus, config)
        if sys.platform != "win32":
            _logger.warning("taskbar_hud plugin is only supported on Windows (win32). Skipping initialization.")
            return

        pipe_name = config.get("pipe_name", "CasterTaskbarHud")
        self._bridge = TaskbarHudBridgeClient.get_instance(pipe_name=pipe_name)

        # 1. Register delegating printer message handler
        self._print_handler = TaskbarHudPrintHandler(bridge=self._bridge)
        printer.get_delegating_handler().register_handler(self._print_handler)

        # 2. Register mic state observer on EngineModesManager
        if nexus and hasattr(nexus, "engine_modes_manager") and nexus.engine_modes_manager:
            nexus.engine_modes_manager.add_mic_listener(self._on_mic_mode_changed)

        # 3. Optionally attach to ADCE context listener if ADCE plugin is loaded
        try:
            from adce import add_context_listener

            add_context_listener(self._on_adce_context_changed)
        except Exception:
            try:
                from caster_user_content.plugins.adce import add_context_listener

                add_context_listener(self._on_adce_context_changed)
            except Exception:
                pass

    def _on_mic_mode_changed(self, mode):
        """Dispatches mic state transitions to Taskbar HUD."""
        if not self._bridge:
            return
        status = "sleeping" if mode in ("sleeping", "off") else "idle"
        command = "Sleeping" if mode in ("sleeping", "off") else "Ready"
        self._bridge.send_update(
            mic_state=mode,
            status=status,
            command=command,
        )

    def _on_adce_context_changed(
        self, process_name="", window_title="", semantic_zone="", active_file="", is_connected=True
    ):
        """Forwards ADCE sub-window zone transitions and active rules to Taskbar HUD."""
        self._adce_connected = bool(is_connected)
        if not self._bridge:
            return
        zone = semantic_zone if (is_connected and semantic_zone) else "--"
        rules_str = "Global"
        if is_connected and process_name:
            try:
                active = resolve_active_rules(
                    process_name=process_name,
                    window_title=window_title,
                    semantic_zone=semantic_zone,
                )
                rules_str = ", ".join(active) if active else "Global"
            except Exception as ex:
                _logger.debug("Context resolution error: %s", ex)
        if self._bridge._cached_rules != rules_str or self._bridge._cached_zone != zone:
            print("[Taskbar HUD] Focus: '{}' -> Rules: '{}' | Zone: '{}'".format(process_name, rules_str, zone))
        self._bridge.send_update(adce_zone=zone, rules=rules_str)

    def start(self):
        super(TaskbarHudPlugin, self).start()
        if sys.platform != "win32":
            return
        self._running = True

        if self._bridge:
            self._bridge.start()

            # Push initial baseline state immediately on startup
            current_mic = "on"
            if self._nexus and hasattr(self._nexus, "engine_modes_manager") and self._nexus.engine_modes_manager:
                current_mic = self._nexus.engine_modes_manager.get_mic_mode() or "on"

            status = "sleeping" if current_mic in ("sleeping", "off") else "idle"
            command = "Sleeping" if current_mic in ("sleeping", "off") else "Ready"

            proc, title = _get_foreground_window_info()
            active = resolve_active_rules(process_name=proc, window_title=title, semantic_zone="")
            rules_str = ", ".join(active) if active else "Global"

            self._bridge.send_update(
                mic_state=current_mic,
                status=status,
                command=command,
                rules=rules_str,
                adce_zone="--",
            )

        # Start fallback window watcher loop when ADCE is not connected/disabled
        self._watcher_thread = threading.Thread(
            target=self._fallback_watcher_loop,
            name="TaskbarHUD-FallbackWindowWatcher",
            daemon=True,
        )
        self._watcher_thread.start()

    def _fallback_watcher_loop(self):
        """Polls foreground window changes when ADCE is offline or disabled."""
        last_proc = None
        last_title = None

        while self._running:
            if not self._adce_connected and self._bridge:
                try:
                    proc, title = _get_foreground_window_info()
                    if proc != last_proc or title != last_title:
                        last_proc = proc
                        last_title = title
                        active = resolve_active_rules(
                            process_name=proc,
                            window_title=title,
                            semantic_zone="",
                        )
                        rules_str = ", ".join(active) if active else "Global"
                        if self._bridge._cached_rules != rules_str:
                            _logger.debug("[Taskbar HUD Fallback] Focus: '%s' -> Rules: '%s'", proc, rules_str)
                        self._bridge.send_update(rules=rules_str, adce_zone="--")
                except Exception as ex:
                    _logger.debug("Fallback window watcher exception: %s", ex)
            time.sleep(0.15)

    def stop(self):
        super(TaskbarHudPlugin, self).stop()
        self._running = False
        if self._bridge:
            self._bridge.stop()
        if self._print_handler:
            printer.get_delegating_handler().unregister_handler(self._print_handler)
            self._print_handler = None
        if self._nexus and hasattr(self._nexus, "engine_modes_manager") and self._nexus.engine_modes_manager:
            self._nexus.engine_modes_manager.remove_mic_listener(self._on_mic_mode_changed)


def get_plugin():
    return TaskbarHudPlugin()
