# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Caster Plugin Manager Plugin lifecycle implementation.
"""

import logging
from typing import Any, List, Optional

try:
    from castervoice.lib.plugin import PluginBase
except ImportError:
    try:
        from plugins.common.plugin_base import PluginBase
    except ImportError:
        from ..common.plugin_base import PluginBase

from .core.ipc_server import PluginManagerIpcServer
from .core.registry import PluginRegistry
from .runner_bridge import close_manager

_logger = logging.getLogger("caster.plugins.plugin_manager")


class PluginManagerPlugin(PluginBase):
    name = "plugin_manager"
    version = "1.0.0"
    description = "Plugin manager GUI and headless registry engine for external Caster plugins."

    def __init__(self):
        super(PluginManagerPlugin, self).__init__()
        self._registry = PluginRegistry()
        self._ipc_server: Optional[PluginManagerIpcServer] = None

    @property
    def registry(self) -> PluginRegistry:
        return self._registry

    @property
    def ipc_server(self) -> Optional[PluginManagerIpcServer]:
        return self._ipc_server

    def initialize(self, nexus, config):
        super(PluginManagerPlugin, self).initialize(nexus, config)
        cfg = config if isinstance(config, dict) else {}
        port = int(cfg.get("ipc_port", 8344))
        self._ipc_server = PluginManagerIpcServer(nexus=nexus, port=port)
        _logger.info("PluginManagerPlugin initialized with IPC server on port %d.", port)

    def start(self):
        super(PluginManagerPlugin, self).start()
        self._registry.scan()
        if self._ipc_server:
            self._ipc_server.start()
        _logger.info("PluginManagerPlugin started. Discovered %d plugins.", len(self._registry.get_plugins()))

    def stop(self):
        super(PluginManagerPlugin, self).stop()
        if self._ipc_server:
            self._ipc_server.stop()
        close_manager()
        _logger.info("PluginManagerPlugin stopped.")

    def get_rules(self) -> List[Any]:
        """Returns companion voice rules when plugin is active."""
        try:
            from .rules import get_rule
            return [get_rule()]
        except Exception as ex:
            _logger.warning("Failed to load Plugin Manager companion rule: %s", ex)
            return []


def get_plugin():
    return PluginManagerPlugin()
