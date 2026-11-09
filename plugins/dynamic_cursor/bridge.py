# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Dynamic Cursor Named Pipe Bridge Client.

Maintains visual layer states and dispatches length-prefixed JSON frames
to the native Dynamic Cursor daemon using the shared NamedPipeTransport.
"""

import logging
import threading
from typing import List, Optional

try:
    from plugins.common.named_pipe import LengthPrefixedFraming, NamedPipeTransport
except ImportError:
    try:
        from ..common.named_pipe import LengthPrefixedFraming, NamedPipeTransport
    except ImportError:
        from caster_user_content.plugins.common.named_pipe import (
            LengthPrefixedFraming,
            NamedPipeTransport,
        )

_logger = logging.getLogger("caster.plugins.dynamic_cursor.bridge")

_SENTINEL = object()


class DynamicCursorBridgeClient(object):
    """
    Bridge client dispatching length-prefixed visual layer frames
    to the native Dynamic Cursor daemon via Named Pipe IPC.
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
        self._enable_mic_tint = bool(enable_mic_tint)
        self._enable_context_badges = bool(enable_context_badges)
        self._listening_tint = str(listening_tint)
        self._sleeping_tint = str(sleeping_tint)
        self._muted_tint = str(muted_tint)

        self._last_sent_mic_payload = None
        self._last_sent_badge_id = _SENTINEL
        self._cached_mic_payload = None
        self._cached_context_payload = None

        self._transport = NamedPipeTransport(
            pipe_name=pipe_name,
            framing=LengthPrefixedFraming(),
            replay_provider=self._get_replay_payloads,
            on_stop_payload={"op": "clear"},
        )
        self._queue = self._transport.queue

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
        return LengthPrefixedFraming().encode(payload)

    @property
    def is_running(self) -> bool:
        """Indicates whether the transport sender loop is running."""
        return self._transport.is_running

    def start(self) -> None:
        """Starts the transport background worker thread."""
        self._transport.start()

    def stop(self) -> None:
        """Dispatches a clear frame and stops the transport worker thread."""
        self._enqueue({"op": "clear"})
        self._transport.stop()

    def clear_layers(self) -> None:
        """Resets cached layers and dispatches a clear operation."""
        with self._lock:
            self._last_sent_mic_payload = None
            self._last_sent_badge_id = _SENTINEL
            self._cached_mic_payload = None
            self._cached_context_payload = None
        self._enqueue({"op": "clear"})

    def flush(self, timeout: float = 1.0) -> bool:
        """Flushes queued frames to the native cursor daemon."""
        return self._transport.flush(timeout=timeout)

    def update_mic_layer(self, mic_state: str) -> None:
        """
        Updates cursor tint layer based on microphone state.

        Deduplicates against the last sent payload and caches state for replay.
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
        Updates context badge layer based on active focus zone.

        Deduplicates against the last sent badge identifier and caches state for replay.
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
        """Enqueues payload for transmission via the underlying transport."""
        self._transport.send(payload)

    def _get_replay_payloads(self) -> List[dict]:
        """Provides snapshot of active layers for transport replay on connect."""
        replays = []
        with self._lock:
            if self._cached_mic_payload is not None:
                replays.append(self._cached_mic_payload)
            if self._cached_context_payload is not None:
                replays.append(self._cached_context_payload)
        return replays


def get_dynamic_cursor_bridge(
    pipe_name: str = "dynamic_cursor",
    **kwargs,
) -> DynamicCursorBridgeClient:
    """Returns singleton DynamicCursorBridgeClient instance."""
    return DynamicCursorBridgeClient.get_instance(pipe_name=pipe_name, **kwargs)
