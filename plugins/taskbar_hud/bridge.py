# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Caster Taskbar HUD Named Pipe Bridge Client.

Provides low-latency telemetry transmission from Caster and ADCE
to the Windows 11 Taskbar HUD Windhawk mod via Named Pipes with NDJSON framing.
"""

import logging
import threading
import time
from typing import List, Optional, Union

try:
    from plugins.common.named_pipe import NamedPipeTransport, NdjsonFraming
except ImportError:
    try:
        from ..common.named_pipe import NamedPipeTransport, NdjsonFraming
    except ImportError:
        from caster_user_content.plugins.common.named_pipe import (
            NamedPipeTransport,
            NdjsonFraming,
        )

_logger = logging.getLogger("caster.plugins.taskbar_hud.bridge")


class TaskbarHudBridgeClient(object):
    """
    Bridge client dispatching NDJSON telemetry frames to the Windows 11 Taskbar HUD mod.
    """

    _instance = None
    _lock = threading.RLock()

    def __init__(self, pipe_name: str = "CasterTaskbarHud"):
        self._pipe_name = pipe_name
        self._state_lock = threading.RLock()

        self._cached_zone = "--"
        self._cached_rules = "Global"
        self._cached_command = "Ready"
        self._cached_status = "idle"
        self._cached_mic_state = "on"

        self._transport = NamedPipeTransport(
            pipe_name=pipe_name,
            framing=NdjsonFraming(),
            replay_provider=self._get_replay_payloads,
        )
        self._queue = self._transport.queue

    @classmethod
    def get_instance(cls, pipe_name: str = "CasterTaskbarHud") -> "TaskbarHudBridgeClient":
        """Returns or creates the singleton bridge client instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = TaskbarHudBridgeClient(pipe_name=pipe_name)
        return cls._instance

    @property
    def is_running(self) -> bool:
        """Indicates whether the transport background thread is running."""
        return self._transport.is_running

    @property
    def is_connected(self) -> bool:
        """Indicates whether the pipe handle is currently open and healthy."""
        return self._transport.is_connected

    def start(self) -> None:
        """Starts the background sender worker thread."""
        self._transport.start()

    def stop(self) -> None:
        """Stops the background sender thread."""
        self._transport.stop()

    def flush(self, timeout: float = 1.0) -> bool:
        """Flushes queued telemetry packets through the transport."""
        return self._transport.flush(timeout=timeout)

    def send_update(
        self,
        command: Optional[str] = None,
        rules: Optional[Union[str, List[str]]] = None,
        adce_zone: Optional[str] = None,
        status: Optional[str] = None,
        mic_state: Optional[str] = None,
    ) -> None:
        """
        Thread-safe state update and transmission.

        Updates cached telemetry state and dispatches an NDJSON packet via the transport layer.
        """
        with self._state_lock:
            if mic_state is not None:
                self._cached_mic_state = str(mic_state)

            if command is not None:
                self._cached_command = str(command)

            if rules is not None:
                if isinstance(rules, str):
                    self._cached_rules = rules.strip() or "Global"
                elif isinstance(rules, (list, tuple, set)):
                    self._cached_rules = ", ".join(rules) if rules else "Global"
                else:
                    self._cached_rules = "Global"

            if adce_zone is not None:
                self._cached_zone = str(adce_zone)

            if status is not None:
                self._cached_status = str(status)

            packet = {
                "mic_state": self._cached_mic_state,
                "command": self._cached_command,
                "rules": self._cached_rules,
                "adce_zone": self._cached_zone,
                "status": self._cached_status,
                "timestamp_ms": int(time.time() * 1000),
            }

        self._transport.send(packet)

    def send_command(self, command: str, status: str = "recognized") -> None:
        """Convenience method dispatching recognized voice command."""
        self.send_update(command=command, status=status)

    def send_zone(self, zone: str) -> None:
        """Convenience method dispatching ADCE focus zone."""
        self.send_update(adce_zone=zone)

    def send_rules(self, rules: Union[str, List[str]]) -> None:
        """Convenience method dispatching active rule set."""
        self.send_update(rules=rules)

    def _get_replay_payloads(self) -> List[dict]:
        """Provides a complete snapshot of cached telemetry state for replay on connect."""
        with self._state_lock:
            return [{
                "mic_state": self._cached_mic_state,
                "command": self._cached_command,
                "rules": self._cached_rules,
                "adce_zone": self._cached_zone,
                "status": self._cached_status,
                "timestamp_ms": int(time.time() * 1000),
            }]


def get_taskbar_hud_bridge(pipe_name: str = "CasterTaskbarHud") -> TaskbarHudBridgeClient:
    """Returns singleton TaskbarHudBridgeClient instance."""
    return TaskbarHudBridgeClient.get_instance(pipe_name=pipe_name)
