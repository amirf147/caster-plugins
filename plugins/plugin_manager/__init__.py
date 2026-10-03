# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Caster Plugin Manager package.
Provides discovery, validation, state management, and configuration interfaces
for external Caster plugins.
"""

from .core.models import PluginHealthState, PluginMetadata, PluginRecord
from .core.registry import PluginRegistry
from .plugin import PluginManagerPlugin, get_plugin

__all__ = [
    "PluginHealthState",
    "PluginManagerPlugin",
    "PluginMetadata",
    "PluginRecord",
    "PluginRegistry",
    "get_plugin",
]
