# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Context-to-Badge Mapper for Dynamic Cursor.

Pure deterministic mapping from active application process names and ADCE
sub-window semantic zones to procedural corner badge identifiers.
"""

import os
from typing import Optional

BROWSER_PROCESS_NAMES = {
    "waterfox",
    "firefox",
    "chrome",
    "msedge",
    "brave",
    "vivaldi",
    "arc",
    "opera",
    "tor",
}

IDE_PROCESS_NAMES = {
    "antigravity",
    "antigravity ide",
    "code",
    "code - oss",
    "vscodium",
    "cursor",
    "windsurf",
    "devenv",
    "pycharm64",
    "idea64",
    "clion64",
    "rider64",
    "nvim",
    "vim",
    "sublime_text",
    "zed",
}

TERMINAL_PROCESS_NAMES = {
    "windowsterminal",
    "wt",
    "pwsh",
    "powershell",
    "cmd",
    "alacritty",
    "wezterm-gui",
    "wezterm",
    "mintty",
    "conhost",
    "git-bash",
}

WRITING_PROCESS_NAMES = {
    "notepad",
    "winword",
    "obsidian",
    "notion",
    "wordpad",
    "typora",
    "soffice.bin",
    "libreoffice",
    "scrivener",
    "logseq",
}

_TERMINAL_ZONES = {"terminal", "integratedterminal", "2"}
_WEB_ZONES = {"webdocument", "documentcontent", "addressbar", "5", "6"}
_WRITING_ZONES = {
    "chatprompt",
    "chatconversation",
    "chatassistant",
    "gitcommitbox",
    "3",
    "11",
    "18",
}
_EDITOR_ZONES = {"editorbuffer", "editorcodebuffer", "1"}


def resolve_context_badge(
    process_name: str,
    semantic_zone: str = "",
    window_title: str = "",
) -> Optional[str]:
    """
    Resolves the appropriate corner badge identifier for the active context.

    Evaluates sub-window semantic focus zone first. Falls back to application
    process name classification when zone is unassigned or generic.
    """
    proc = os.path.basename(str(process_name or "").strip()).lower()
    if proc.endswith(".exe"):
        proc = proc[:-4]

    norm_zone = str(semantic_zone or "").strip().lower().replace("_", "").replace(" ", "")

    # Stage 1: Sub-window semantic zone priority
    if norm_zone in _TERMINAL_ZONES:
        return "terminal_prompt"

    if norm_zone in _WEB_ZONES:
        return "web_globe"

    if norm_zone in _WRITING_ZONES:
        return "doc_writing"

    if norm_zone in _EDITOR_ZONES:
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
