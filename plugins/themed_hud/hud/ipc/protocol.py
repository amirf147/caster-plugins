"""
Newline-Delimited JSON (ndjson) Stream Protocol for IPC Framing.
Prevents TCP message boundary tearing and partial chunk parsing errors.
"""

import json
from typing import Iterator, Dict, Any, Union

from hud.core.events import HudEvent


def encode_event(event: Union[HudEvent, Dict[str, Any]]) -> bytes:
    """Encode a HudEvent or dictionary into a newline-terminated UTF-8 byte string."""
    if isinstance(event, HudEvent):
        payload = event.to_dict()
    else:
        payload = event
    json_str = json.dumps(payload, separators=(',', ':'))
    return (json_str + "\n").encode("utf-8")


class NdjsonStreamDecoder:
    """
    Streaming buffer decoder that ingests arbitrary socket chunks and yields
    complete, validated JSON event dictionaries.
    """

    def __init__(self, max_buffer_size: int = 1048576):
        self._buffer = bytearray()
        self._max_buffer_size = max_buffer_size

    def feed(self, chunk: bytes) -> Iterator[Dict[str, Any]]:
        """Feed a raw byte chunk from socket and yield all complete JSON objects."""
        if not chunk:
            return

        self._buffer.extend(chunk)
        if len(self._buffer) > self._max_buffer_size:
            # Prevent memory overflow on corrupted stream
            self._buffer.clear()
            return

        while True:
            newline_pos = self._buffer.find(b"\n")
            if newline_pos == -1:
                break

            line_bytes = self._buffer[:newline_pos].strip()
            del self._buffer[:newline_pos + 1]

            if not line_bytes:
                continue

            try:
                line_str = line_bytes.decode("utf-8")
                parsed = json.loads(line_str)
                if isinstance(parsed, dict):
                    yield parsed
            except (UnicodeDecodeError, json.JSONDecodeError):
                # Ignore malformed frame and continue
                continue

    def clear(self):
        """Reset internal buffer state."""
        self._buffer.clear()
