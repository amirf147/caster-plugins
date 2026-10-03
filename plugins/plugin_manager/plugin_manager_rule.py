# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Dragonfly voice commands for Caster Plugin Manager.
Provides deterministic, unbranched command grammar specs.
"""

from typing import Tuple

try:
    from dragonfly import Function, MappingRule
except ImportError:
    # Dummy fallback classes for environments where dragonfly is not installed
    class MappingRule:  # type: ignore[no-redef]
        mapping = {}

    def Function(fn):  # type: ignore[misc] # noqa: N802
        return fn

try:
    from castervoice.lib.ctrl.mgr.rule_details import RuleDetails
except ImportError:
    class RuleDetails:  # type: ignore[no-redef]
        def __init__(self, name=""):
            self.name = name

from .runner_bridge import close_manager, open_manager_process, refresh_manager


def _cmd_open_manager():
    open_manager_process()


def _cmd_refresh_manager():
    refresh_manager()


def _cmd_close_manager():
    close_manager()


class PluginManagerRule(MappingRule):
    """
    Companion voice grammar rule for Plugin Manager.
    Defines deterministic, unbranched command specs.
    """
    mapping = {
        "plugin manager": Function(_cmd_open_manager),
        "plugin manager refresh": Function(_cmd_refresh_manager),
        "plugin manager close": Function(_cmd_close_manager),
    }


def get_rule():
    details = RuleDetails(name="plugin manager")
    return PluginManagerRule, details
