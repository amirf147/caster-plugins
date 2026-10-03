# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Loopback XML-RPC client connecting the Plugin Manager GUI subprocess
to Caster's live host engine process.
"""

import logging
import socket
from typing import Optional, Set, Tuple
import xmlrpc.client

from .ipc_server import DEFAULT_IPC_HOST, DEFAULT_IPC_PORT

_logger = logging.getLogger("caster.plugins.plugin_manager.ipc_client")


class TimeoutTransport(xmlrpc.client.Transport):
    """Custom XML-RPC transport supporting socket timeouts to avoid GUI thread hangs."""

    def __init__(self, timeout: float = 0.5, use_datetime: bool = False, use_builtin_types: bool = False):
        super().__init__(use_datetime=use_datetime, use_builtin_types=use_builtin_types)
        self._timeout = timeout

    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self._timeout
        return conn


class PluginManagerIpcClient:
    """
    Client interface providing dynamic control over Caster's running plugins.
    Gracefully handles offline engine state when Caster is not active.
    """

    def __init__(
        self,
        host: str = DEFAULT_IPC_HOST,
        port: int = DEFAULT_IPC_PORT,
        timeout_seconds: float = 0.5,
    ):
        self._host = host
        self._port = port
        self._timeout = timeout_seconds
        self._uri = f"http://{self._host}:{self._port}"
        self._proxy: Optional[xmlrpc.client.ServerProxy] = None

    def _get_proxy(self) -> xmlrpc.client.ServerProxy:
        """Returns or creates ServerProxy configured with socket timeout."""
        if self._proxy is None:
            transport = TimeoutTransport(timeout=self._timeout)
            self._proxy = xmlrpc.client.ServerProxy(self._uri, transport=transport, allow_none=True)
        return self._proxy

    def is_connected(self) -> bool:
        """Returns True if Caster engine IPC server is reachable, else False."""
        try:
            proxy = self._get_proxy()
            return bool(proxy.ping())
        except (socket.error, ConnectionRefusedError, TimeoutError, OSError, Exception):
            return False

    def get_running_plugins(self) -> Set[str]:
        """Queries the set of actively executing plugin names in Caster."""
        try:
            proxy = self._get_proxy()
            names = proxy.get_running_plugins()
            return set(names) if isinstance(names, list) else set()
        except Exception as ex:
            _logger.debug("Failed to query running plugins via IPC: %s", ex)
            return set()

    def load_plugin(self, name: str) -> Tuple[bool, str]:
        """Requests Caster engine to dynamically instantiate, initialize, and start a plugin."""
        try:
            proxy = self._get_proxy()
            res = proxy.load_plugin(name)
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                return bool(res[0]), str(res[1])
            return bool(res), f"Plugin '{name}' load command executed."
        except Exception as ex:
            return False, f"IPC load command failed: {ex}"

    def unload_plugin(self, name: str) -> Tuple[bool, str]:
        """Requests Caster engine to stop and unload a plugin."""
        try:
            proxy = self._get_proxy()
            res = proxy.unload_plugin(name)
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                return bool(res[0]), str(res[1])
            return bool(res), f"Plugin '{name}' unload command executed."
        except Exception as ex:
            return False, f"IPC unload command failed: {ex}"

    def reload_all(self) -> Tuple[bool, str]:
        """Requests Caster engine to reload all enabled plugins."""
        try:
            proxy = self._get_proxy()
            res = proxy.reload_all()
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                return bool(res[0]), str(res[1])
            return bool(res), "Reload all command executed."
        except Exception as ex:
            return False, f"IPC reload_all command failed: {ex}"
