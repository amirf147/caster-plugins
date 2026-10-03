# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Taskbar HUD Plugin

Integrates Caster voice recognition and mic telemetry with the Windows 11
Taskbar HUD Windhawk mod via Named Pipe with event-driven Win32 hooks
and two-phase context resolution.
"""

import ctypes
from ctypes import wintypes
import logging
import os
import queue
import sys
import threading
import time

from castervoice.lib import printer
try:
    from castervoice.lib.plugin import PluginBase
except ImportError:
    try:
        from plugins.common.plugin_base import PluginBase
    except ImportError:
        from ..common.plugin_base import PluginBase
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
EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000
WINEVENT_SKIPOWNPROCESS = 0x0002
WM_QUIT = 0x0012

if _user32:
    WinEventProcType = ctypes.WINFUNCTYPE(
        None,
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.HWND,
        wintypes.LONG,
        wintypes.LONG,
        wintypes.DWORD,
        wintypes.DWORD,
    )
else:
    WinEventProcType = None


def _get_foreground_window_info(target_hwnd=None):
    """Returns (process_name, window_title, hwnd) for active foreground window via native Win32."""
    try:
        if not _user32 or not _kernel32:
            return "", "", 0

        hwnd = target_hwnd or _user32.GetForegroundWindow()
        if not hwnd:
            return "", "", 0

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
            return "", title, hwnd

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

        return proc_name, title, hwnd
    except Exception as ex:
        _logger.debug("Error querying foreground window info: %s", ex)
        return "", "", 0


class TaskbarHudPlugin(PluginBase):
    name = "taskbar_hud"
    version = "1.1.0"
    description = "Windows 11 Taskbar HUD Windhawk Mod Bridge with Decoupled Context Engine"

    def __init__(self):
        super(TaskbarHudPlugin, self).__init__()
        self._bridge = None
        self._print_handler = None
        self._adce_connected = False
        self._running = False

        self._focus_queue = queue.Queue(maxsize=64)
        self._debouncer_thread = None
        self._hook_thread = None
        self._hook_handle = None
        self._hook_proc = None
        self._hook_thread_id = None

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
            _logger.debug("[Taskbar HUD] Focus: '%s' -> Rules: '%s' | Zone: '%s'", process_name, rules_str, zone)
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

            proc, title, hwnd = _get_foreground_window_info()
            active = resolve_active_rules(process_name=proc, window_title=title, semantic_zone="", hwnd=hwnd)
            rules_str = ", ".join(active) if active else "Global"

            self._bridge.send_update(
                mic_state=current_mic,
                status=status,
                command=command,
                rules=rules_str,
                adce_zone="--",
            )

        # 1. Start debounced focus processing worker
        self._debouncer_thread = threading.Thread(
            target=self._focus_debouncer_loop,
            name="TaskbarHUD-FocusDebouncer",
            daemon=True,
        )
        self._debouncer_thread.start()

        # 2. Start event-driven Win32 event hook worker
        if _user32 and WinEventProcType:
            self._hook_thread = threading.Thread(
                target=self._win_event_hook_loop,
                name="TaskbarHUD-WinEventHookThread",
                daemon=True,
            )
            self._hook_thread.start()

    def _win_event_hook_loop(self):
        """Pumps Win32 messages and dispatches EVENT_SYSTEM_FOREGROUND notifications."""
        if not _user32 or not _kernel32:
            return

        self._hook_thread_id = _kernel32.GetCurrentThreadId()

        def _on_win_event(hHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
            if hwnd and self._running and not self._adce_connected:
                try:
                    self._focus_queue.put_nowait(hwnd)
                except queue.Full:
                    pass

        self._hook_proc = WinEventProcType(_on_win_event)
        self._hook_handle = _user32.SetWinEventHook(
            EVENT_SYSTEM_FOREGROUND,
            EVENT_SYSTEM_FOREGROUND,
            0,
            self._hook_proc,
            0,
            0,
            WINEVENT_OUTOFCONTEXT | WINEVENT_SKIPOWNPROCESS,
        )

        if not self._hook_handle:
            _logger.debug("SetWinEventHook failed or returned NULL. Falling back to timer polling.")
            return

        msg = wintypes.MSG()
        while self._running:
            res = _user32.GetMessageW(ctypes.byref(msg), 0, 0, 0)
            if res <= 0:
                break
            _user32.TranslateMessage(ctypes.byref(msg))
            _user32.DispatchMessageW(ctypes.byref(msg))

        if self._hook_handle:
            try:
                _user32.UnhookWinEvent(self._hook_handle)
            except Exception:
                pass
            self._hook_handle = None

    def _focus_debouncer_loop(self):
        """Processes foreground window focus changes with trailing-edge debouncing."""
        last_proc = None
        last_title = None

        while self._running:
            if self._adce_connected:
                time.sleep(0.2)
                continue

            try:
                _ = self._focus_queue.get(timeout=0.1)
            except queue.Empty:
                # If hook is unavailable, perform lightweight polling
                if not self._hook_handle and not self._adce_connected and self._bridge:
                    proc, title, current_hwnd = _get_foreground_window_info()
                    if proc != last_proc or title != last_title:
                        last_proc = proc
                        last_title = title
                        self._dispatch_focus_update(proc, title, current_hwnd)
                continue

            # Trailing-edge debounce: drain burst focus events within 40ms window
            time.sleep(0.04)
            while not self._focus_queue.empty():
                try:
                    self._focus_queue.get_nowait()
                except queue.Empty:
                    break

            if not self._adce_connected and self._bridge:
                proc, title, current_hwnd = _get_foreground_window_info()
                if proc != last_proc or title != last_title:
                    last_proc = proc
                    last_title = title
                    self._dispatch_focus_update(proc, title, current_hwnd)

    def _dispatch_focus_update(self, proc: str, title: str, hwnd: int):
        """Resolves active rules and dispatches NDJSON frame to Taskbar HUD bridge."""
        if not proc and not title:
            return
        try:
            active = resolve_active_rules(
                process_name=proc,
                window_title=title,
                semantic_zone="",
                hwnd=hwnd,
            )
            rules_str = ", ".join(active) if active else "Global"
            if self._bridge and self._bridge._cached_rules != rules_str:
                _logger.debug("[Taskbar HUD] Focus: '%s' -> Rules: '%s'", proc, rules_str)
            if self._bridge:
                self._bridge.send_update(rules=rules_str, adce_zone="--")
        except Exception as ex:
            _logger.debug("Focus update dispatch error: %s", ex)

    def stop(self):
        super(TaskbarHudPlugin, self).stop()
        self._running = False

        if self._hook_thread_id and _user32:
            try:
                _user32.PostThreadMessageW(self._hook_thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass

        if self._bridge:
            self._bridge.stop()
        if self._print_handler:
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
            self._nexus.engine_modes_manager.remove_mic_listener(self._on_mic_mode_changed)


def get_plugin():
    return TaskbarHudPlugin()
