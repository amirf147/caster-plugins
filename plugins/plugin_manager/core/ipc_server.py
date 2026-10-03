# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Loopback XML-RPC server exposing Caster's internal PluginManager lifecycle API
to external child processes (e.g., Plugin Manager GUI).
"""

import logging
import threading
from typing import Any, List, Optional, Tuple
from xmlrpc.server import SimpleXMLRPCServer

_logger = logging.getLogger("caster.plugins.plugin_manager.ipc_server")

DEFAULT_IPC_HOST = "127.0.0.1"
DEFAULT_IPC_PORT = 8344


class PluginManagerIpcServer:
    """
    Thread-safe XML-RPC server dispatching remote control calls directly into Caster's PluginManager.
    """

    def __init__(self, nexus: Optional[Any] = None, host: str = DEFAULT_IPC_HOST, port: int = DEFAULT_IPC_PORT):
        self._nexus = nexus
        self._host = host
        self._port = port
        self._server: Optional[SimpleXMLRPCServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.RLock()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def port(self) -> int:
        return self._port

    def set_nexus(self, nexus: Any):
        """Updates nexus reference for Caster manager interaction."""
        with self._lock:
            self._nexus = nexus

    def _get_caster_plugin_manager(self) -> Optional[Any]:
        """Resolves the global Caster PluginManager instance."""
        try:
            from castervoice.lib.ctrl.mgr.plugin_manager import get_plugin_manager
            return get_plugin_manager(nexus=self._nexus)
        except Exception as ex:
            _logger.debug("Failed to obtain Caster plugin manager: %s", ex)
            return None

    # RPC Endpoints
    def ping(self) -> bool:
        """Health-check endpoint returning True when engine host is active."""
        return True

    def get_running_plugins(self) -> List[str]:
        """Returns list of plugin names currently loaded and executing in Caster."""
        pm = self._get_caster_plugin_manager()
        if pm is None:
            return []
        try:
            return [p.name for p in pm.get_loaded_plugins() if getattr(p, "is_running", False)]
        except Exception as ex:
            _logger.warning("Error fetching loaded plugins: %s", ex)
            return []

    def load_plugin(self, name: str) -> Tuple[bool, str]:
        """Dynamically loads, initializes, and starts a plugin inside Caster."""
        pm = self._get_caster_plugin_manager()
        if pm is None:
            return False, "Caster PluginManager instance is unavailable."
        try:
            return pm.load_plugin(name)
        except Exception as ex:
            _logger.exception("Error loading plugin '%s':", name)
            return False, f"Exception loading plugin '{name}': {ex}"

    def unload_plugin(self, name: str) -> Tuple[bool, str]:
        """Stops and unloads an active plugin from Caster."""
        pm = self._get_caster_plugin_manager()
        if pm is None:
            return False, "Caster PluginManager instance is unavailable."
        try:
            return pm.unload_plugin(name)
        except Exception as ex:
            _logger.exception("Error unloading plugin '%s':", name)
            return False, f"Exception unloading plugin '{name}': {ex}"

    def reload_all(self) -> Tuple[bool, str]:
        """Stops, refreshes settings, and reloads all enabled plugins."""
        pm = self._get_caster_plugin_manager()
        if pm is None:
            return False, "Caster PluginManager instance is unavailable."
        try:
            return pm.reload_all()
        except Exception as ex:
            _logger.exception("Error reloading all plugins:")
            return False, f"Exception reloading plugins: {ex}"

    def start(self) -> bool:
        """Starts the XML-RPC server on a background daemon thread."""
        with self._lock:
            if self._running:
                return True

            try:
                server = SimpleXMLRPCServer(
                    (self._host, self._port),
                    logRequests=False,
                    allow_none=True,
                )
                server.register_function(self.ping, "ping")
                server.register_function(self.get_running_plugins, "get_running_plugins")
                server.register_function(self.load_plugin, "load_plugin")
                server.register_function(self.unload_plugin, "unload_plugin")
                server.register_function(self.reload_all, "reload_all")

                self._server = server
                self._running = True

                self._thread = threading.Thread(
                    target=self._server_loop,
                    name="PluginManagerIpcServerThread",
                    daemon=True,
                )
                self._thread.start()
                _logger.info("PluginManagerIpcServer started on %s:%d", self._host, self._port)
                return True
            except Exception as ex:
                _logger.warning("Failed to start PluginManagerIpcServer on port %d: %s", self._port, ex)
                self._running = False
                self._server = None
                return False

    def _server_loop(self):
        """Internal server loop executing in background thread."""
        try:
            if self._server:
                self._server.serve_forever()
        except Exception as ex:
            _logger.debug("IPC server loop terminated: %s", ex)
        finally:
            self._running = False

    def stop(self):
        """Stops the XML-RPC server and shuts down the background thread."""
        with self._lock:
            if not self._running:
                return

            self._running = False
            if self._server:
                try:
                    self._server.shutdown()
                    self._server.server_close()
                except Exception as ex:
                    _logger.debug("Error closing IPC server socket: %s", ex)
                self._server = None

            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
            self._thread = None
            _logger.info("PluginManagerIpcServer stopped.")
