# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Context-to-Badge Mapper for Dynamic Cursor.

Pure deterministic mapping from active application process names and canonical
semantic focus zones to procedural corner badge identifiers.
"""

import os
from typing import Optional

try:
    from plugins.common.desktop_context import (
        BROWSER_PROCESS_NAMES,
        IDE_PROCESS_NAMES,
        TERMINAL_PROCESS_NAMES,
        WRITING_PROCESS_NAMES,
        SemanticZone,
        canonicalize_zone,
    )
except ImportError:
    try:
        from ..common.desktop_context import (
            BROWSER_PROCESS_NAMES,
            IDE_PROCESS_NAMES,
            TERMINAL_PROCESS_NAMES,
            WRITING_PROCESS_NAMES,
            SemanticZone,
            canonicalize_zone,
        )
    except ImportError:
        from enum import Enum

        class SemanticZone(str, Enum):
            EDITOR = "editor"
            TERMINAL = "terminal"
            DOCUMENT = "document"
            WEB = "web"
            CHAT = "chat"
            UNKNOWN = "unknown"

        def canonicalize_zone(raw):
            return str(raw or "").lower()

        BROWSER_PROCESS_NAMES = frozenset(["firefox", "chrome", "msedge", "waterfox"])
        IDE_PROCESS_NAMES = frozenset(["code", "cursor", "antigravity"])
        TERMINAL_PROCESS_NAMES = frozenset(["windowsterminal", "pwsh", "cmd"])
        WRITING_PROCESS_NAMES = frozenset(["notepad", "winword", "obsidian"])

__all__ = [
    "BROWSER_PROCESS_NAMES",
    "IDE_PROCESS_NAMES",
    "TERMINAL_PROCESS_NAMES",
    "WRITING_PROCESS_NAMES",
    "resolve_context_badge",
]


def resolve_context_badge(
    process_name: str,
    semantic_zone: str = "",
    window_title: str = "",
) -> Optional[str]:
    """
    Resolves the appropriate corner badge identifier for the active context.

    Evaluates sub-window semantic focus zone first using canonical SemanticZone.
    Falls back to application process name classification when zone is unassigned or generic.
    """
    proc = os.path.basename(str(process_name or "").strip()).lower()
    if proc.endswith(".exe"):
        proc = proc[:-4]

    canon_zone = canonicalize_zone(semantic_zone)

    # Stage 1: Sub-window canonical semantic zone priority
    if canon_zone == SemanticZone.TERMINAL:
        return "terminal_prompt"

    if canon_zone == SemanticZone.WEB:
        return "web_globe"

    if canon_zone in (SemanticZone.DOCUMENT, SemanticZone.CHAT):
        return "doc_writing"

    if canon_zone == SemanticZone.EDITOR:
        if proc in WRITING_PROCESS_NAMES:
            return "doc_writing"
        if proc in BROWSER_PROCESS_NAMES:
            return "web_globe"
        return "code_brackets"

    # Stage 2: Application process name fallback
    if proc in BROWSER_PROCESS_NAMES:
        return "web_globe"

    if proc in TERMINAL_PROCESS_NAMES:
        return "terminal_prompt"

    if proc in IDE_PROCESS_NAMES:
        return "code_brackets"

    if proc in WRITING_PROCESS_NAMES:
        return "doc_writing"

    return None
