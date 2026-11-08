# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Dynamic Cursor Named Pipe Bridge Client.

Maintains an asynchronous worker thread and bounded queue for dispatching
length-prefixed JSON visual layer frames to the native Dynamic Cursor daemon.
"""

import ctypes
from ctypes import wintypes
import json
import logging
import queue
import struct
import sys
import threading
import time
from typing import Optional

_logger = logging.getLogger("caster.plugins.dynamic_cursor.bridge")

GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x80

if sys.platform == "win32":
    _kernel32 = ctypes.windll.kernel32
    INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
else:
    _kernel32 = None
    INVALID_HANDLE_VALUE = -1

_SENTINEL = object()


class DynamicCursorBridgeClient:
    """
    Singleton client maintaining an asynchronous queue and background worker
    for pushing length-prefixed JSON frames to \\\\.\\pipe\\<pipe_name>.
    """

    _instance = None
    _lock = threading.RLock()

    def __init__(
        self,
        pipe_name: str = "dynamic_cursor",
        enable_mic_tint: bool = True,
        enable_context_badges: bool = True,
        listening_tint: str = "#44FF66",
        sleeping_tint: str = "#FF5555",
        muted_tint: str = "#888888",
    ):
        self._pipe_name = pipe_name
        self._pipe_path = f"\\\\.\\pipe\\{pipe_name}"
        self._enable_mic_tint = bool(enable_mic_tint)
        self._enable_context_badges = bool(enable_context_badges)
        self._listening_tint = str(listening_tint)
        self._sleeping_tint = str(sleeping_tint)
        self._muted_tint = str(muted_tint)

        self._queue = queue.Queue(maxsize=128)
        self._running = False
        self._worker_thread = None

        self._last_sent_mic_payload = None
        self._last_sent_badge_id = _SENTINEL
        self._cached_mic_payload = None
        self._cached_context_payload = None

    @classmethod
    def get_instance(
        cls,
        pipe_name: str = "dynamic_cursor",
        **kwargs,
    ) -> "DynamicCursorBridgeClient":
        """Returns or creates the singleton bridge client instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(pipe_name=pipe_name, **kwargs)
        return cls._instance

    @staticmethod
    def encode_frame(payload: dict) -> bytes:
        """Serializes dictionary payload to length-prefixed UTF-8 JSON bytes."""
        utf8_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        prefix = struct.pack("<I", len(utf8_bytes))
        return prefix + utf8_bytes

    def start(self):
        """Starts the background worker thread for Named Pipe transmission."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._worker_thread = threading.Thread(
                target=self._sender_loop,
                name="DynamicCursor-NamedPipe-Worker",
                daemon=True,
            )
            self._worker_thread.start()

    def stop(self):
        """Stops the worker thread and dispatches a clear operation."""
        with self._lock:
            was_running = self._running
            self._running = False

        self._enqueue({"op": "clear"})

        if was_running and self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
            self._worker_thread = None

    def update_mic_layer(self, mic_state: str) -> None:
        """
        Updates the primary cursor body tint layer according to mic mode.

        Deduplicates against the last sent payload and maintains cached state
        for automatic reconnection replay.
        """
        norm_state = str(mic_state or "").strip().lower()

        if not self._enable_mic_tint:
            payload = {"op": "remove", "layer_id": "caster_mic"}
        elif norm_state in ("on", "listening", "active"):
            payload = {
                "op": "upsert",
                "layer_id": "caster_mic",
                "priority": 80,
                "tint_rgba": self._listening_tint,
            }
        elif norm_state in ("sleeping", "standby"):
            payload = {
                "op": "upsert",
                "layer_id": "caster_mic",
                "priority": 80,
                "tint_rgba": self._sleeping_tint,
            }
        elif norm_state in ("off", "muted"):
            payload = {
                "op": "upsert",
                "layer_id": "caster_mic",
                "priority": 80,
                "tint_rgba": self._muted_tint,
                "badge_id": "mic_off",
            }
        else:
            payload = {
                "op": "upsert",
                "layer_id": "caster_mic",
                "priority": 80,
                "tint_rgba": self._listening_tint,
            }

        with self._lock:
            if payload == self._last_sent_mic_payload:
                return
            self._last_sent_mic_payload = payload
            self._cached_mic_payload = payload

        self._enqueue(payload)

    def update_context_layer(self, badge_id: Optional[str]) -> None:
        """
        Updates the secondary corner badge layer according to focus context.

        Deduplicates against the last sent badge identifier and dispatches
        removal when badge_id is None or badges are disabled.
        """
        with self._lock:
            if badge_id == self._last_sent_badge_id:
                return
            self._last_sent_badge_id = badge_id

            if badge_id is None or not self._enable_context_badges:
                payload = {"op": "remove", "layer_id": "adce_context"}
            else:
                payload = {
                    "op": "upsert",
                    "layer_id": "adce_context",
                    "priority": 30,
                    "badge_id": str(badge_id),
                }
            self._cached_context_payload = payload

        self._enqueue(payload)

    def _enqueue(self, payload: dict) -> None:
        """Enqueues a payload frame with bounded drop-oldest overflow handling."""
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            try:
                _ = self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(payload)
            except queue.Full:
                pass

    def _sender_loop(self):
        """Worker loop managing connection lifecycle and frame writing."""
        handle = INVALID_HANDLE_VALUE
        pending_frame = None

        while self._running:
            if pending_frame is None:
                try:
                    payload = self._queue.get(timeout=0.25)
                except queue.Empty:
                    continue
                pending_frame = self.encode_frame(payload)

            if _kernel32 is None:
                pending_frame = None
                continue

            if handle == INVALID_HANDLE_VALUE or handle == 0 or handle is None:
                handle = _kernel32.CreateFileW(
                    self._pipe_path,
                    GENERIC_WRITE,
                    0,
                    None,
                    OPEN_EXISTING,
                    0,
                    None,
                )
                if handle == INVALID_HANDLE_VALUE or handle == 0 or handle is None:
                    handle = INVALID_HANDLE_VALUE
                    time.sleep(0.1)
                    continue

                self._replay_cached_states(handle)

            if not self._write_raw_bytes(handle, pending_frame):
                _kernel32.CloseHandle(handle)
                handle = INVALID_HANDLE_VALUE
                time.sleep(0.1)
            else:
                _kernel32.FlushFileBuffers(handle)
                pending_frame = None

        if _kernel32 and handle != INVALID_HANDLE_VALUE and handle != 0 and handle is not None:
            try:
                clear_frame = self.encode_frame({"op": "clear"})
                self._write_raw_bytes(handle, clear_frame)
                _kernel32.FlushFileBuffers(handle)
            except Exception:
                pass
            finally:
                _kernel32.CloseHandle(handle)

    def _replay_cached_states(self, handle) -> None:
        """Replays current mic and context state layers on new connection."""
        replays = []
        with self._lock:
            if self._cached_mic_payload is not None:
                replays.append(self._cached_mic_payload)
            if self._cached_context_payload is not None:
                replays.append(self._cached_context_payload)

        for payload in replays:
            frame = self.encode_frame(payload)
            if not self._write_raw_bytes(handle, frame):
                break

    def _write_raw_bytes(self, handle, data: bytes) -> bool:
        """Writes buffer bytes to the open pipe handle."""
        if not _kernel32 or handle == INVALID_HANDLE_VALUE or handle == 0 or handle is None:
            return False

        total = 0
        length = len(data)
        while total < length:
            chunk = data[total:]
            to_write = len(chunk)
            written = wintypes.DWORD(0)
            ok = _kernel32.WriteFile(
                handle,
                chunk,
                to_write,
                ctypes.byref(written),
                None,
            )
            if not ok or written.value == 0:
                return False
            total += written.value
        return True


def get_dynamic_cursor_bridge(
    pipe_name: str = "dynamic_cursor",
    **kwargs,
) -> DynamicCursorBridgeClient:
    """Returns singleton DynamicCursorBridgeClient instance."""
    return DynamicCursorBridgeClient.get_instance(pipe_name=pipe_name, **kwargs)
