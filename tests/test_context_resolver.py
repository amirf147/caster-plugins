# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Unit tests for the Automated Rule Catalog & Universal Context Resolver.
Verifies dynamic AST parsing, multi-tiered path discovery, and rules.toml synchronization.
"""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from plugins.taskbar_hud.context_resolver import (
    RuleCatalog,
    format_display_name,
    normalize_process_name,
    resolve_active_rules as taskbar_resolve,
    resolve_caster_user_dir,
    resolve_rule_search_dirs,
    resolve_rules_config_path,
)
from plugins.themed_hud.context_resolver import (
    resolve_active_rules as themed_resolve,
)


class TestContextResolver(unittest.TestCase):

    def test_normalize_process_name(self):
        self.assertEqual(normalize_process_name("C:\\Program Files\\Code.exe"), "code")
        self.assertEqual(normalize_process_name("/usr/bin/firefox"), "firefox")
        self.assertEqual(normalize_process_name("WATERFOX.EXE"), "waterfox")
        self.assertEqual(normalize_process_name(""), "")
        self.assertEqual(normalize_process_name(None), "")

    def test_format_display_name(self):
        # Strips 'Rule' and handles CCR
        self.assertEqual(format_display_name("CustomVSCodeRule", "CustomVSCodeRule"), "CustomVSCode")
        self.assertEqual(format_display_name("CustomVSCode CCR", "CustomVSCodeCcrRule"), "CustomVSCode CCR")
        self.assertEqual(format_display_name(None, "CustomVSCodeCcrRule"), "CustomVSCode CCR")
        self.assertEqual(format_display_name("fire fox rule", "FirefoxRule"), "Firefox")

    def test_path_discovery_resilience(self):
        user_dir = resolve_caster_user_dir()
        self.assertIsNotNone(user_dir)
        self.assertTrue(user_dir.exists())

        cfg_path = resolve_rules_config_path(user_dir)
        if cfg_path:
            self.assertTrue(cfg_path.exists())

        dirs = resolve_rule_search_dirs(user_dir)
        self.assertGreater(len(dirs), 0)
        for d in dirs:
            self.assertTrue(d.exists())

    def test_catalog_ast_extraction(self):
        catalog = RuleCatalog()
        self.assertGreater(len(catalog._proc_map), 0)

        # code.exe should resolve to editor rules
        rules = catalog.resolve(process_name="code.exe", window_title="test.py - Visual Studio Code")
        self.assertTrue(any("CustomVSCode" in r for r in rules))

        # Title matching: waterfox with Gemini title
        rules_site = catalog.resolve(process_name="waterfox.exe", window_title="Google Gemini - Waterfox")
        self.assertTrue(any("Gemini" in r for r in rules_site))
        self.assertTrue(any("Firefox" in r for r in rules_site))

        # Empty context returns empty list
        self.assertEqual(catalog.resolve(process_name="", window_title=""), [])
        self.assertEqual(catalog.resolve(process_name=None, window_title=None), [])

    def test_parity_between_taskbar_and_themed_hud(self):
        """Verifies both taskbar_hud and themed_hud resolvers produce identical output."""
        procs = ["code.exe", "waterfox.exe", "explorer.exe", "windowsterminal.exe"]
        titles = ["main.py", "Google Gemini", "Downloads", "Windows PowerShell"]

        for proc, title in zip(procs, titles):
            t_res = taskbar_resolve(process_name=proc, window_title=title)
            th_res = themed_resolve(process_name=proc, window_title=title)
            self.assertEqual(t_res, th_res, f"Mismatch for proc={proc}, title={title}")


if __name__ == "__main__":
    unittest.main()
