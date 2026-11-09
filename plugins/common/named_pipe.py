# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Shared Named Pipe Transport and Framing Abstractions.

Provides high-performance, bounded, asynchronous Named Pipe communication
for Caster plugin clients on Windows with 64-bit safe ctypes declarations,
reconnection backoff, and pluggable framing abstractions.
"""

import json
import logging
import queue
import struct
import sys
import threading
import time
from typing import Any, Callable, Iterable, List, Optional, Union

_logger = logging.getLogger("caster.plugins.common.named_pipe")

# Windows ctypes declarations with 64-bit safety
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.windll.kernel32

    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80
    INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value

    _kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _kernel32.CreateFileW.restype = wintypes.HANDLE

    _kernel32.WriteFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_char_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    _kernel32.WriteFile.restype = wintypes.BOOL

    _kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    _kernel32.FlushFileBuffers.restype = wintypes.BOOL

    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
else:
    _kernel32 = None
    GENERIC_WRITE = 0
    OPEN_EXISTING = 0
    FILE_ATTRIBUTE_NORMAL = 0
    INVALID_HANDLE_VALUE = -1


class LengthPrefixedFraming(object):
    """
    Length-prefixed binary framing.

    Encodes each frame as a 4-byte little-endian unsigned 32-bit integer length prefix
    followed by the UTF-8 encoded payload bytes.
    """

    max_batch_size = 1

    def encode(self, payload: Any) -> bytes:
        if isinstance(payload, bytes):
            utf8_bytes = payload
        elif isinstance(payload, str):
            utf8_bytes = payload.encode("utf-8")
        else:
            utf8_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        prefix = struct.pack("<I", len(utf8_bytes))
        return prefix + utf8_bytes

    def encode_batch(self, payloads: List[Any]) -> bytes:
        return b"".join(self.encode(item) for item in payloads)


class NdjsonFraming(object):
    """
    Newline-delimited JSON framing.

    Encodes payloads as newline-terminated UTF-8 JSON lines, batching up to 16 frames per write.
    """

    max_batch_size = 16

    def encode(self, payload: Any) -> bytes:
        if isinstance(payload, bytes):
            line = payload.decode("utf-8")
        elif isinstance(payload, str):
            line = payload
        else:
            line = json.dumps(payload)
        if not line.endswith("\n"):
            line = line + "\n"
        return line.encode("utf-8")

    def encode_batch(self, payloads: List[Any]) -> bytes:
        return b"".join(self.encode(item) for item in payloads)


class NamedPipeTransport(object):
    """
    Thread-safe Named Pipe transport client.

    Manages a dedicated background sender thread, drop-oldest bounded queuing,
    automatic connection retries with exponential backoff, and state snapshot replay on connect.
    """

    def __init__(
        self,
        pipe_name: str,
        framing: Optional[Any] = None,
        replay_provider: Optional[Union[Callable[[], Iterable[Any]], Iterable[Any]]] = None,
        on_stop_payload: Optional[Any] = None,
        max_queue_size: int = 128,
        min_backoff: float = 0.05,
        max_backoff: float = 1.0,
        backoff_factor: float = 1.5,
    ):
        self._pipe_name = pipe_name
        if pipe_name.startswith("\\\\.\\pipe\\"):
            self._pipe_path = pipe_name
        else:
            self._pipe_path = f"\\\\.\\pipe\\{pipe_name}"

        self._framing = framing if framing is not None else LengthPrefixedFraming()
        self._replay_provider = replay_provider
        self._on_stop_payload = on_stop_payload
        self._max_queue_size = max_queue_size
        self._min_backoff = min_backoff
        self._max_backoff = max_backoff
        self._backoff_factor = backoff_factor

        self._queue = queue.Queue(maxsize=max_queue_size)
        self._lifecycle_lock = threading.RLock()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._connected = False

    @property
    def queue(self) -> queue.Queue:
        """Returns the internal bounded queue."""
        return self._queue

    @property
    def is_running(self) -> bool:
        """Returns True if the worker thread is active."""
        return self._running

    @property
    def is_connected(self) -> bool:
        """Returns True if the pipe handle is currently open and healthy."""
        return self._connected

    def start(self) -> None:
        """Starts the dedicated background worker thread."""
        with self._lifecycle_lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._worker_thread = threading.Thread(
                target=self._sender_loop,
                name=f"NamedPipeTransport-{self._pipe_name}",
                daemon=True,
            )
            self._worker_thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        """Stops the worker thread and cleans up active resources."""
        with self._lifecycle_lock:
            if not self._running:
                return
            self._running = False
            self._stop_event.set()
            worker = self._worker_thread
            self._worker_thread = None

        if worker and worker.is_alive():
            worker.join(timeout=timeout)

    def send(self, payload: Any) -> bool:
        """
        Enqueues payload for transmission using drop-oldest overflow policy.

        Returns True if enqueued successfully, or False if queue was unrecoverable.
        """
        try:
            self._queue.put_nowait(payload)
            return True
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(payload)
                return True
            except queue.Full:
                return False

    def flush(self, timeout: float = 1.0) -> bool:
        """Waits up to timeout seconds for queued payloads to be written."""
        deadline = time.time() + timeout
        while not self._queue.empty():
            if time.time() > deadline:
                return False
            time.sleep(0.01)
        return True

    def _sender_loop(self) -> None:
        """Background worker consuming queue items and writing to Named Pipe."""
        handle = INVALID_HANDLE_VALUE
        pending_bytes: Optional[bytes] = None
        current_backoff = self._min_backoff

        while self._running:
            if pending_bytes is None:
                try:
                    first_item = self._queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                items = [first_item]
                batch_limit = getattr(self._framing, "max_batch_size", 1)
                while not self._queue.empty() and len(items) < batch_limit:
                    try:
                        items.append(self._queue.get_nowait())
                    except queue.Empty:
                        break

                try:
                    if hasattr(self._framing, "encode_batch"):
                        pending_bytes = self._framing.encode_batch(items)
                    else:
                        pending_bytes = b"".join(self._framing.encode(item) for item in items)
                except Exception as ex:
                    _logger.debug("Framing encode error: %s", ex)
                    pending_bytes = None
                    continue

            if sys.platform != "win32" and _kernel32 is None:
                pending_bytes = None
                self._stop_event.wait(timeout=0.25)
                continue

            if not self._is_valid_handle(handle):
                self._connected = False
                handle = self._open_pipe()
                if not self._is_valid_handle(handle):
                    handle = INVALID_HANDLE_VALUE
                    self._stop_event.wait(timeout=current_backoff)
                    current_backoff = min(current_backoff * self._backoff_factor, self._max_backoff)
                    continue

                current_backoff = self._min_backoff
                self._connected = True

                if not self._replay_cached_state(handle):
                    self._close_handle(handle)
                    handle = INVALID_HANDLE_VALUE
                    self._connected = False
                    self._stop_event.wait(timeout=current_backoff)
                    current_backoff = min(current_backoff * self._backoff_factor, self._max_backoff)
                    continue

            if not self._write_bytes(handle, pending_bytes):
                self._close_handle(handle)
                handle = INVALID_HANDLE_VALUE
                self._connected = False
                self._stop_event.wait(timeout=current_backoff)
                current_backoff = min(current_backoff * self._backoff_factor, self._max_backoff)
            else:
                self._flush_handle(handle)
                pending_bytes = None

        if self._is_valid_handle(handle):
            if self._on_stop_payload is not None:
                try:
                    stop_bytes = self._framing.encode(self._on_stop_payload)
                    self._write_bytes(handle, stop_bytes)
                    self._flush_handle(handle)
                except Exception as ex:
                    _logger.debug("Failed to write on_stop payload: %s", ex)
            self._close_handle(handle)
            self._connected = False

    def _replay_cached_state(self, handle: Any) -> bool:
        """Transmits cached state payloads to a newly opened pipe handle."""
        if self._replay_provider is None:
            return True

        try:
            if callable(self._replay_provider):
                items = self._replay_provider()
            else:
                items = self._replay_provider

            if not items:
                return True

            items_list = list(items) if isinstance(items, (list, tuple)) else [items]
            if not items_list:
                return True

            batch_limit = getattr(self._framing, "max_batch_size", 1)
            if batch_limit > 1 and hasattr(self._framing, "encode_batch"):
                data = self._framing.encode_batch(items_list)
                if not self._write_bytes(handle, data):
                    return False
            else:
                for item in items_list:
                    data = self._framing.encode(item)
                    if not self._write_bytes(handle, data):
                        return False

            self._flush_handle(handle)
            return True
        except Exception as ex:
            _logger.debug("Replay cached state failed: %s", ex)
            return False

    def _open_pipe(self) -> Any:
        """Opens a handle to the configured Named Pipe path."""
        if not _kernel32:
            return INVALID_HANDLE_VALUE
        return _kernel32.CreateFileW(
            self._pipe_path,
            GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            0,
            None,
        )

    def _write_bytes(self, handle: Any, data: bytes) -> bool:
        """Writes buffer bytes to the open pipe handle."""
        if not _kernel32 or not self._is_valid_handle(handle):
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

    def _flush_handle(self, handle: Any) -> bool:
        """Flushes the pipe buffer to disk/remote end."""
        if not _kernel32 or not self._is_valid_handle(handle):
            return False
        return bool(_kernel32.FlushFileBuffers(handle))

    def _close_handle(self, handle: Any) -> bool:
        """Closes the Win32 handle."""
        if not _kernel32 or not self._is_valid_handle(handle):
            return False
        return bool(_kernel32.CloseHandle(handle))

    def _is_valid_handle(self, handle: Any) -> bool:
        """Validates handle against null, zero, negative, and invalid representations."""
        if handle is None or handle == 0 or handle == -1:
            return False
        if handle == INVALID_HANDLE_VALUE:
            return False
        return True
