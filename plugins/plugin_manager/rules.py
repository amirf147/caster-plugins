# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Compatibility re-export layer for Plugin Manager voice rules.
"""

from .plugin_manager_rule import (
    PluginManagerRule,
    RuleDetails,
    get_rule,
    _cmd_open_manager,
    _cmd_refresh_manager,
    _cmd_close_manager,
)

__all__ = [
    "PluginManagerRule",
    "RuleDetails",
    "get_rule",
]
