# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Dynamic Cursor Plugin for Caster.

Integrates Caster microphone telemetry and Active Desktop Context Engine (ADCE)
semantic focus zones with the native Windows hardware cursor via Named Pipe IPC.
"""

import ctypes
from ctypes import wintypes
import logging
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
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

from .bridge import DynamicCursorBridgeClient
from .context_mapper import resolve_context_badge
from .printer_handler import DynamicCursorPrintHandler

_logger = logging.getLogger("caster.plugins.dynamic_cursor")

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
    _user32.SetWinEventHook.restype = wintypes.HANDLE
    _user32.SetWinEventHook.argtypes = [
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HMODULE,
        WinEventProcType,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    _user32.UnhookWinEvent.restype = wintypes.BOOL
    _user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
else:
    WinEventProcType = None


def _get_foreground_window_info(target_hwnd=None):
    """Returns (process_name, window_title, hwnd) for active foreground window."""
    try:
        if not _user32 or not _kernel32:
            return "", "", 0

        hwnd = target_hwnd or _user32.GetForegroundWindow()
        if not hwnd:
            return "", "", 0

        length = _user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value

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

        self._focus_queue = queue.Queue(maxsize=64)
        self._debouncer_thread = None
        self._hook_thread = None
        self._hook_handle = None
        self._hook_proc = None
        self._hook_thread_id = None

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

    def start(self):
        """Starts background worker threads and dispatches baseline states."""
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

            proc, title, _ = _get_foreground_window_info()
            initial_badge = resolve_context_badge(proc, "", title)
            self._bridge.update_context_layer(initial_badge)

        self._debouncer_thread = threading.Thread(
            target=self._focus_debouncer_loop,
            name="DynamicCursor-FocusDebouncer",
            daemon=True,
        )
        self._debouncer_thread.start()

        if _user32 and WinEventProcType:
            self._hook_thread = threading.Thread(
                target=self._win_event_hook_loop,
                name="DynamicCursor-WinEventHookThread",
                daemon=True,
            )
            self._hook_thread.start()

    def _win_event_hook_loop(self):
        """Pumps Win32 messages and captures EVENT_SYSTEM_FOREGROUND transitions."""
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
            _logger.debug("SetWinEventHook failed or returned NULL.")
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
        """Drains focus events with trailing-edge debouncing when ADCE is disconnected."""
        last_proc = None

        while self._running:
            if self._adce_connected:
                time.sleep(0.2)
                continue

            try:
                _ = self._focus_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            time.sleep(0.04)
            while not self._focus_queue.empty():
                try:
                    self._focus_queue.get_nowait()
                except queue.Empty:
                    break

            if not self._adce_connected and self._bridge:
                proc, title, _ = _get_foreground_window_info()
                if proc != last_proc:
                    last_proc = proc
                    badge_id = resolve_context_badge(proc, "", title)
                    self._bridge.update_context_layer(badge_id)

    def stop(self):
        """Performs clean teardown of hooks, message pumps, and bridge client."""
        super(DynamicCursorPlugin, self).stop()
        self._running = False

        if self._hook_thread_id and _user32:
            try:
                _user32.PostThreadMessageW(self._hook_thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass

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
