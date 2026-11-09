# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Unified Desktop Context Provider and Canonical Semantic Zone Engine.

Maintains a single authoritative stream of desktop context snapshots combining
native Win32 foreground window tracking with Active Desktop Context Engine (ADCE)
semantic sub-window focus.
"""

from dataclasses import dataclass
from enum import Enum
import logging
import os
import queue
import sys
import threading
import time
from typing import Callable, List, Optional, Tuple

_logger = logging.getLogger("caster.plugins.common.desktop_context")

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    EVENT_SYSTEM_FOREGROUND = 0x0003
    WINEVENT_OUTOFCONTEXT = 0x0000
    WINEVENT_SKIPOWNPROCESS = 0x0002
    WM_QUIT = 0x0012

    WINEVENTPROC = ctypes.WINFUNCTYPE(
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
        WINEVENTPROC,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
    ]

    _user32.UnhookWinEvent.restype = wintypes.BOOL
    _user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]

    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetForegroundWindow.argtypes = []

    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]

    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]

    _user32.GetClassNameW.restype = ctypes.c_int
    _user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

    _user32.PostThreadMessageW.restype = wintypes.BOOL
    _user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]

    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    _kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    _kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]

    _kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    _kernel32.GetCurrentThreadId.argtypes = []
else:
    _user32 = None
    _kernel32 = None
    WINEVENTPROC = None

_SHELL_EXCLUDED_CLASSES = frozenset(
    [
        "XamlExplorerHostIslandWindow",
        "TaskSwitcherWnd",
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "Progman",
        "WorkerW",
        "Windows.UI.Core.CoreWindow",
        "DV2ControlHost",
    ]
)

BROWSER_PROCESS_NAMES = frozenset(
    [
        "waterfox",
        "firefox",
        "chrome",
        "msedge",
        "brave",
        "vivaldi",
        "arc",
        "opera",
        "tor",
    ]
)

IDE_PROCESS_NAMES = frozenset(
    [
        "antigravity",
        "antigravity ide",
        "code",
        "code - oss",
        "vscodium",
        "cursor",
        "windsurf",
        "devenv",
        "pycharm64",
        "idea64",
        "clion64",
        "rider64",
        "nvim",
        "vim",
        "sublime_text",
        "zed",
    ]
)

TERMINAL_PROCESS_NAMES = frozenset(
    [
        "windowsterminal",
        "wt",
        "pwsh",
        "powershell",
        "cmd",
        "alacritty",
        "wezterm-gui",
        "wezterm",
        "mintty",
        "conhost",
        "git-bash",
    ]
)

WRITING_PROCESS_NAMES = frozenset(
    [
        "notepad",
        "winword",
        "obsidian",
        "notion",
        "wordpad",
        "typora",
        "soffice.bin",
        "libreoffice",
        "scrivener",
        "logseq",
    ]
)


class SemanticZone(str, Enum):
    """Canonical desktop semantic focus zones."""

    EDITOR = "editor"
    TERMINAL = "terminal"
    DOCUMENT = "document"
    WEB = "web"
    CHAT = "chat"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


_ZONE_CANONICAL_MAP = {
    # Editor zones
    "1": SemanticZone.EDITOR,
    "editor": SemanticZone.EDITOR,
    "editorbuffer": SemanticZone.EDITOR,
    "editorcodebuffer": SemanticZone.EDITOR,
    "codeeditor": SemanticZone.EDITOR,
    "editorpane": SemanticZone.EDITOR,
    # Terminal zones
    "2": SemanticZone.TERMINAL,
    "terminal": SemanticZone.TERMINAL,
    "integratedterminal": SemanticZone.TERMINAL,
    "console": SemanticZone.TERMINAL,
    "shell": SemanticZone.TERMINAL,
    # Document and writing zones
    "3": SemanticZone.DOCUMENT,
    "18": SemanticZone.DOCUMENT,
    "document": SemanticZone.DOCUMENT,
    "doc": SemanticZone.DOCUMENT,
    "writing": SemanticZone.DOCUMENT,
    "gitcommitbox": SemanticZone.DOCUMENT,
    "notes": SemanticZone.DOCUMENT,
    # Web and browser zones
    "5": SemanticZone.WEB,
    "6": SemanticZone.WEB,
    "web": SemanticZone.WEB,
    "webdocument": SemanticZone.WEB,
    "documentcontent": SemanticZone.WEB,
    "addressbar": SemanticZone.WEB,
    "browser": SemanticZone.WEB,
    # Chat and AI assistant zones
    "11": SemanticZone.CHAT,
    "chat": SemanticZone.CHAT,
    "chatprompt": SemanticZone.CHAT,
    "chatconversation": SemanticZone.CHAT,
    "chatassistant": SemanticZone.CHAT,
    "assistant": SemanticZone.CHAT,
    # Unknown
    "unknown": SemanticZone.UNKNOWN,
    "--": SemanticZone.UNKNOWN,
}


def canonicalize_zone(raw_zone: Optional[str]) -> str:
    """
    Maps raw ADCE integer strings, synonyms, and variants to canonical SemanticZone values.
    """
    if not raw_zone:
        return SemanticZone.UNKNOWN
    norm = str(raw_zone).strip().lower().replace("_", "").replace(" ", "").replace("-", "")
    return _ZONE_CANONICAL_MAP.get(norm, SemanticZone.UNKNOWN)


def classify_process_zone(proc_name: str) -> str:
    """
    Maps process executable names to fallback semantic zones when ADCE is disconnected.
    """
    proc = os.path.basename(str(proc_name or "").strip()).lower()
    if proc.endswith(".exe"):
        proc = proc[:-4]
    if proc in TERMINAL_PROCESS_NAMES:
        return SemanticZone.TERMINAL
    if proc in IDE_PROCESS_NAMES:
        return SemanticZone.EDITOR
    if proc in BROWSER_PROCESS_NAMES:
        return SemanticZone.WEB
    if proc in WRITING_PROCESS_NAMES:
        return SemanticZone.DOCUMENT
    return SemanticZone.UNKNOWN


def _get_foreground_window_info(target_hwnd: Optional[int] = None) -> Tuple[str, str, int]:
    """
    Queries foreground window metadata using safe Win32 API calls.
    """
    if sys.platform != "win32" or not _user32 or not _kernel32:
        return "", "", 0

    try:
        hwnd = target_hwnd or _user32.GetForegroundWindow()
        if not hwnd:
            return "", "", 0

        # Exclude shell desktop and taskbar classes
        class_buf = ctypes.create_unicode_buffer(256)
        if _user32.GetClassNameW(hwnd, class_buf, 256):
            if class_buf.value in _SHELL_EXCLUDED_CLASSES:
                return "", "", 0

        # Window title retrieval
        length = _user32.GetWindowTextLengthW(hwnd)
        title = ""
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value

        # Process name retrieval via PID
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


@dataclass(frozen=True)
class ContextSnapshot:
    """Immutable representation of desktop context state."""

    hwnd: int = 0
    process_name: str = ""
    window_title: str = ""
    semantic_zone: str = SemanticZone.UNKNOWN
    active_file: str = ""
    terminal_shell: str = ""
    is_adce_connected: bool = False


class DesktopContextProvider:
    """
    Authoritative desktop context provider combining Win32 hooks with ADCE SSE telemetry.
    """

    _instance: Optional["DesktopContextProvider"] = None
    _lock = threading.RLock()

    def __init__(self):
        self._listeners: List[Callable[[ContextSnapshot], None]] = []
        self._current_snapshot = ContextSnapshot()
        self._focus_queue: queue.Queue[int] = queue.Queue(maxsize=128)
        self._running = False

        self._hook_thread: Optional[threading.Thread] = None
        self._debouncer_thread: Optional[threading.Thread] = None
        self._hook_handle = None
        self._hook_proc = None
        self._hook_thread_id: Optional[int] = None

    @classmethod
    def get_instance(cls) -> "DesktopContextProvider":
        """Returns the process-wide singleton provider instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = DesktopContextProvider()
        return cls._instance

    @classmethod
    def _reset_for_testing(cls) -> None:
        """Internal helper to reset singleton state between unit tests."""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.stop()
                cls._instance = None

    def get_current_snapshot(self) -> ContextSnapshot:
        """Returns the current immutable snapshot."""
        with self._lock:
            return self._current_snapshot

    def add_listener(self, callback: Callable[[ContextSnapshot], None]) -> None:
        """
        Registers a context listener callback.
        Immediately invokes the callback with the current snapshot to prevent startup races.
        """
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)
            snapshot = self._current_snapshot

        if not self._running and sys.platform == "win32":
            self.start()

        try:
            callback(snapshot)
        except Exception as ex:
            _logger.debug("Error invoking initial callback in add_listener: %s", ex)

    def remove_listener(self, callback: Callable[[ContextSnapshot], None]) -> None:
        """Removes a registered context listener callback."""
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def update_adce_context(
        self,
        semantic_zone: str = "",
        active_file: str = "",
        terminal_shell: str = "",
        is_connected: bool = False,
        process_name: str = "",
        window_title: str = "",
    ) -> None:
        """
        Updates context when ADCE connects, receives SSE telemetry, or disconnects.
        Preserves foreground window identity when disconnecting rather than clearing to blanks.
        """
        with self._lock:
            prev = self._current_snapshot
            hwnd = prev.hwnd
            proc = process_name if process_name else prev.process_name
            title = window_title if window_title else prev.window_title

            if not proc and sys.platform == "win32":
                fg_proc, fg_title, fg_hwnd = _get_foreground_window_info()
                if fg_proc:
                    proc, title, hwnd = fg_proc, fg_title, fg_hwnd

            if is_connected:
                zone = canonicalize_zone(semantic_zone)
                if zone == SemanticZone.UNKNOWN and proc:
                    fallback = classify_process_zone(proc)
                    if fallback != SemanticZone.UNKNOWN:
                        zone = fallback

                new_snapshot = ContextSnapshot(
                    hwnd=hwnd,
                    process_name=proc,
                    window_title=title,
                    semantic_zone=zone,
                    active_file=active_file,
                    terminal_shell=terminal_shell,
                    is_adce_connected=True,
                )
            else:
                zone = classify_process_zone(proc) if proc else SemanticZone.UNKNOWN
                new_snapshot = ContextSnapshot(
                    hwnd=hwnd,
                    process_name=proc,
                    window_title=title,
                    semantic_zone=zone,
                    active_file="",
                    terminal_shell="",
                    is_adce_connected=False,
                )

            if new_snapshot == prev:
                return

            self._current_snapshot = new_snapshot
            listeners = list(self._listeners)

        for cb in listeners:
            try:
                cb(new_snapshot)
            except Exception as ex:
                _logger.debug("Error in context snapshot listener: %s", ex)

    def start(self) -> None:
        """Starts background Win32 message hook and focus debouncer loops."""
        if sys.platform != "win32":
            return

        with self._lock:
            if self._running:
                return
            self._running = True

            proc, title, hwnd = _get_foreground_window_info()
            if proc or hwnd:
                zone = classify_process_zone(proc)
                self._current_snapshot = ContextSnapshot(
                    hwnd=hwnd,
                    process_name=proc,
                    window_title=title,
                    semantic_zone=zone,
                    is_adce_connected=False,
                )

            self._debouncer_thread = threading.Thread(
                target=self._focus_debouncer_loop,
                name="DesktopContext-Debouncer",
                daemon=True,
            )
            self._debouncer_thread.start()

            if _user32 and WINEVENTPROC:
                self._hook_thread = threading.Thread(
                    target=self._win_event_hook_loop,
                    name="DesktopContext-WinEventHook",
                    daemon=True,
                )
                self._hook_thread.start()

    def _win_event_hook_loop(self) -> None:
        """Pumps Win32 messages and captures EVENT_SYSTEM_FOREGROUND notifications."""
        if not _user32 or not _kernel32:
            return

        self._hook_thread_id = _kernel32.GetCurrentThreadId()

        def _on_win_event(hHook, event, hwnd, idObject, idChild, dwEventThread, dwmsEventTime):
            if hwnd and self._running:
                try:
                    self._focus_queue.put_nowait(hwnd)
                except queue.Full:
                    pass

        self._hook_proc = WINEVENTPROC(_on_win_event)
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
            _logger.debug("SetWinEventHook returned NULL in DesktopContextProvider.")
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

    def _focus_debouncer_loop(self) -> None:
        """Processes foreground window focus changes with 40 ms trailing-edge debouncing."""
        while self._running:
            try:
                _ = self._focus_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            time.sleep(0.040)
            while not self._focus_queue.empty():
                try:
                    self._focus_queue.get_nowait()
                except queue.Empty:
                    break

            proc, title, current_hwnd = _get_foreground_window_info()
            if not current_hwnd or not proc:
                continue

            self._handle_foreground_window_changed(current_hwnd, proc, title)

    def _handle_foreground_window_changed(self, hwnd: int, proc: str, title: str) -> None:
        with self._lock:
            prev = self._current_snapshot
            if prev.hwnd == hwnd and prev.process_name == proc and prev.window_title == title:
                return

            if prev.is_adce_connected:
                if proc == prev.process_name:
                    zone = prev.semantic_zone
                    active_file = prev.active_file
                    shell = prev.terminal_shell
                else:
                    zone = classify_process_zone(proc)
                    active_file = ""
                    shell = ""
                is_connected = True
            else:
                zone = classify_process_zone(proc)
                active_file = ""
                shell = ""
                is_connected = False

            new_snapshot = ContextSnapshot(
                hwnd=hwnd,
                process_name=proc,
                window_title=title,
                semantic_zone=zone,
                active_file=active_file,
                terminal_shell=shell,
                is_adce_connected=is_connected,
            )
            self._current_snapshot = new_snapshot
            listeners = list(self._listeners)

        for cb in listeners:
            try:
                cb(new_snapshot)
            except Exception as ex:
                _logger.debug("Error in context snapshot listener: %s", ex)

    def stop(self) -> None:
        """Stops background threads and releases Win32 hooks."""
        self._running = False
        if self._hook_thread_id and _user32:
            try:
                _user32.PostThreadMessageW(self._hook_thread_id, WM_QUIT, 0, 0)
            except Exception:
                pass
