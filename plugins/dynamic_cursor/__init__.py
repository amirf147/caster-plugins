# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Dynamic Cursor Plugin Package.

Projects Caster microphone telemetry and ADCE semantic focus context onto
the native Windows hardware cursor via Named Pipe IPC.
"""

from .bridge import DynamicCursorBridgeClient, get_dynamic_cursor_bridge
from .context_mapper import (
    BROWSER_PROCESS_NAMES,
    IDE_PROCESS_NAMES,
    TERMINAL_PROCESS_NAMES,
    WRITING_PROCESS_NAMES,
    resolve_context_badge,
)
from .plugin import DynamicCursorPlugin, get_plugin
from .printer_handler import DynamicCursorPrintHandler

__all__ = [
    "DynamicCursorPlugin",
    "DynamicCursorBridgeClient",
    "get_dynamic_cursor_bridge",
    "resolve_context_badge",
    "DynamicCursorPrintHandler",
    "get_plugin",
    "BROWSER_PROCESS_NAMES",
    "IDE_PROCESS_NAMES",
    "TERMINAL_PROCESS_NAMES",
    "WRITING_PROCESS_NAMES",
]
