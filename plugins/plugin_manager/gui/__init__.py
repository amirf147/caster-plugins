# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
GUI package for Caster Plugin Manager.
"""

from .runner import show_plugin_manager
from .window import PluginManagerWindow

__all__ = [
    "PluginManagerWindow",
    "show_plugin_manager",
]
