# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Active Desktop Context Engine (ADCE) Plugin

Integrates out-of-process semantic focus context stream into Caster.
"""

import atexit
import logging
import os
import socket
import subprocess
import sys
import time

from castervoice.lib.plugin import PluginBase
from .client import AdceBridgeClient

try:
    from caster_user_content.environment_variables import ADCE_DIRECTORY, ADCE_PROJECT
except ImportError:
    try:
        from environment_variables import ADCE_DIRECTORY, ADCE_PROJECT
    except ImportError:
        ADCE_DIRECTORY = None
        ADCE_PROJECT = "src/ADCE.Daemon"

_logger = logging.getLogger("caster.plugins.adce")


def _is_daemon_alive(host="127.0.0.1", port=8424, timeout=0.5):
    """Checks whether the ADCE daemon is actively listening on host:port."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, socket.error):
        return False


def _terminate_process_tree(pid: int):
    """Cleanly terminates a process and all of its child processes on Windows."""
    if not pid:
        return
    try:
        if sys.platform == "win32":
            # taskkill /F /T kills the specified process and all child processes (e.g. dotnet -> ADCE.Daemon)
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                timeout=3,
                check=False,
            )
    except Exception as ex:
        _logger.debug("Failed to taskkill process tree for PID %s: %s", pid, ex)


def _spawn_daemon(host="127.0.0.1", port=8424, command=None, cwd=None):
    """Spawns the ADCE daemon process detached in the background."""
    if cwd is None and ADCE_DIRECTORY:
        cwd = ADCE_DIRECTORY

    if command is None:
        if ADCE_PROJECT:
            command = ["dotnet", "run", "--project", ADCE_PROJECT]
        else:
            command = ["dotnet", "run"]
    elif isinstance(command, str):
        command = [command]

    creationflags = 0
    if sys.platform == "win32":
        creationflags = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        )

    _logger.info("ADCE daemon not detected on %s:%d. Spawning: %s (cwd=%s)", host, port, command, cwd)
    try:
        proc = subprocess.Popen(
            command,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            shell=False,
        )
        _logger.info("ADCE daemon spawned with PID %s", proc.pid)
        return proc
    except Exception as ex:
        _logger.warning("Failed to auto-spawn ADCE daemon: %s", ex)
        return None


class AdcePlugin(PluginBase):
    name = "adce"
    version = "1.0.0"
    description = "Active Desktop Context Engine (ADCE) SSE Bridge"

    def __init__(self):
        super(AdcePlugin, self).__init__()
        self._client = None
        self._host = "127.0.0.1"
        self._port = 8424
        self._autostart = True
        self._startup_command = None
        self._startup_cwd = None
        self._spawned_proc = None
        self._atexit_registered = False

    def initialize(self, nexus, config):
        super(AdcePlugin, self).initialize(nexus, config)
        self._host = config.get("host", "127.0.0.1")
        self._port = int(config.get("port", 8424))
        self._autostart = bool(config.get("autostart", True))
        self._startup_command = config.get("startup_command", None)
        self._startup_cwd = config.get("startup_cwd", None)
        self._client = AdceBridgeClient.get_instance(host=self._host, port=self._port)

    def start(self):
        super(AdcePlugin, self).start()

        # 1. Probe daemon status and auto-spawn if missing and enabled
        if self._autostart and not _is_daemon_alive(self._host, self._port):
            self._spawned_proc = _spawn_daemon(
                host=self._host,
                port=self._port,
                command=self._startup_command,
                cwd=self._startup_cwd,
            )
            if self._spawned_proc and not self._atexit_registered:
                atexit.register(self._cleanup_spawned_process)
                self._atexit_registered = True
            time.sleep(0.5)

        # 2. Start bridge client connection
        if self._client:
            self._client.start()

    def _cleanup_spawned_process(self):
        """Terminates daemon process tree if spawned by this Caster instance."""
        proc = self._spawned_proc
        self._spawned_proc = None
        if proc is not None:
            try:
                _logger.info("Terminating auto-spawned ADCE daemon process tree (PID %s)...", proc.pid)
                _terminate_process_tree(proc.pid)
                try:
                    proc.wait(timeout=2)
                except Exception:
                    pass
            except Exception as ex:
                _logger.debug("Error during ADCE daemon shutdown: %s", ex)

    def stop(self):
        super(AdcePlugin, self).stop()
        if self._client:
            self._client.stop()
        self._cleanup_spawned_process()


def get_plugin():
    return AdcePlugin()
