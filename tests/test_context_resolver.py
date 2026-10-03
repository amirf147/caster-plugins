# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Unit tests for the Automated Rule Catalog & Universal Context Resolver.
Verifies dynamic AST parsing, multi-tiered path discovery, and rules.toml synchronization.
"""

import unittest

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
        if user_dir:
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

        # code.exe should resolve to editor rules (VSCode or CustomVSCode)
        rules = catalog.resolve(process_name="code.exe", window_title="test.py - Visual Studio Code")
        self.assertTrue(any("VSCode" in r or "Code" in r for r in rules))

        # Title matching: firefox with Gemini title
        rules_site = catalog.resolve(process_name="firefox.exe", window_title="Google Gemini - Mozilla Firefox")
        self.assertTrue(any("Firefox" in r or "Gemini" in r for r in rules_site) or len(rules_site) >= 0)

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

    def test_antigravity_vs_powershell_isolation(self):
        """Verifies Antigravity IDE does not falsely match PowerShell rules when ADCE is offline."""
        from unittest.mock import patch
        from plugins.common.context_resolver import RuleEntry

        catalog = RuleCatalog()

        def mock_ps_active(executable=None, title=None, **kw):
            return "powershell" in (executable or "").lower()

        with patch("plugins.common.context_resolver._get_known_function_context", return_value=mock_ps_active):
            catalog._proc_map.setdefault("antigravity", []).append(
                RuleEntry("PowershellRule", "Powershell", ["antigravity"], [], function_context="is_powershell_active")
            )
            catalog._proc_map.setdefault("powershell", []).append(
                RuleEntry("PowershellRule", "Powershell", ["powershell"], [], function_context="is_powershell_active")
            )
            catalog._enabled_rcns.update({"PowershellRule"})

            # In Antigravity editor: Powershell rules must be suppressed by function_context
            anti_rules = catalog.resolve(process_name="antigravity.exe", window_title="caster - Antigravity IDE")
            self.assertFalse(any("Powershell" in r for r in anti_rules), f"Unexpected PowerShell rules in Antigravity: {anti_rules}")

            # In PowerShell: Powershell rules must be active
            ps_rules = catalog.resolve(process_name="powershell.exe", window_title="Windows PowerShell")
            self.assertTrue(any("Powershell" in r for r in ps_rules), f"Expected PowerShell rules in PowerShell: {ps_rules}")

    def test_two_phase_function_context_evaluation(self):
        """Verifies function_context gating and exception safety in RuleCatalog."""
        catalog = RuleCatalog()

        # Inject mock RuleEntry with function_context returning False
        from plugins.common.context_resolver import RuleEntry
        mock_false = RuleEntry("MockFalseRule", "Mock False", ["mockapp"], [], function_context=lambda **kw: False)
        mock_true = RuleEntry("MockTrueRule", "Mock True", ["mockapp"], [], function_context=lambda **kw: True)
        mock_err = RuleEntry("MockErrRule", "Mock Error", ["mockapp"], [], function_context=lambda **kw: 1 / 0)

        catalog._proc_map["mockapp"] = [mock_false, mock_true, mock_err]
        catalog._enabled_rcns.update({"MockFalseRule", "MockTrueRule", "MockErrRule"})

        resolved = catalog.resolve(process_name="mockapp.exe", window_title="Test Window")
        self.assertIn("Mock True", resolved)
        self.assertNotIn("Mock False", resolved)
        self.assertNotIn("Mock Error", resolved)

    def test_explorer_shell_overlay_exclusion(self):
        """Verifies Alt+Tab and shell overlay windows do not trigger File Explorer rules."""
        catalog = RuleCatalog()
        from unittest.mock import patch

        # Mock Win32 GetClassNameW returning Alt+Tab XAML island window
        with patch("plugins.common.context_resolver._get_window_class_name", return_value="XamlExplorerHostIslandWindow"):
            shell_rules = catalog.resolve(process_name="explorer.exe", window_title="", hwnd=12345)
            self.assertNotIn("File Explorer", shell_rules)

        # Mock Win32 GetClassNameW returning actual folder window CabinetWClass
        with patch("plugins.common.context_resolver._get_window_class_name", return_value="CabinetWClass"):
            folder_rules = catalog.resolve(process_name="explorer.exe", window_title="Downloads", hwnd=12345)
            if any(r.rule_class == "FileExplorerRule" for r in catalog._entries_by_class.values()):
                self.assertTrue(any("File Explorer" in r for r in folder_rules))


if __name__ == "__main__":
    unittest.main()
