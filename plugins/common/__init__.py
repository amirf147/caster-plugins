# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Shared common utilities, plugin base classes, and context resolvers for Caster plugins.
"""

from .plugin_base import PluginBase
from .named_pipe import (
    NamedPipeTransport,
    LengthPrefixedFraming,
    NdjsonFraming,
)
from .desktop_context import (
    DesktopContextProvider,
    ContextSnapshot,
    SemanticZone,
    canonicalize_zone,
    classify_process_zone,
    IDE_PROCESS_NAMES,
    BROWSER_PROCESS_NAMES,
    TERMINAL_PROCESS_NAMES,
    WRITING_PROCESS_NAMES,
)

__all__ = [
    "PluginBase",
    "NamedPipeTransport",
    "LengthPrefixedFraming",
    "NdjsonFraming",
    "DesktopContextProvider",
    "ContextSnapshot",
    "SemanticZone",
    "canonicalize_zone",
    "classify_process_zone",
    "IDE_PROCESS_NAMES",
    "BROWSER_PROCESS_NAMES",
    "TERMINAL_PROCESS_NAMES",
    "WRITING_PROCESS_NAMES",
]
