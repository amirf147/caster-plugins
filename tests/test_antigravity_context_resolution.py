"""
Integration test suite verifying precision context candidate resolution and
rules.toml authoritative active rule filtering in Caster HUD.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from dragonfly import Grammar, MappingRule, get_current_engine
from castervoice.lib.ctrl.mgr.rule_details import RuleDetails
from castervoice.lib.ctrl.mgr.rule_maker.mapping_rule_maker import MappingRuleMaker
try:
    from castervoice.asynch.hud_support import (
        get_active_contextual_rules,
        _match_executable_precision,
        _extract_context_executables,
        _is_rule_enabled_in_config,
    )
    HAS_CORE_SUPPORT = True
except ImportError:
    HAS_CORE_SUPPORT = False

try:
    from caster_user_content.rules.apps.antigravity import AntigravityAppRule, get_rule as get_antigravity_standalone_rule
    from caster_user_content.rules.apps.vscode.antigravity_ide import AntigravityIDERule, get_rule as get_antigravity_ide_rule
    from caster_user_content.rules.apps.vscode.vscode import CustomVSCodeRule, get_rule as get_vscode_rule
    from castervoice.rules.apps.browser.firefox import FirefoxRule, get_rule as get_firefox_rule
    HAS_USER_RULES = True
except ImportError:
    HAS_USER_RULES = False



class MockTransformerRunner:
    def transform_rule(self, rule):
        return rule


class MockSmrConfigurer:
    def configure(self, rule):
        pass


class ManagedRuleMock:
    def __init__(self, rule_class, details):
        self._rule_class = rule_class
        self._details = details

    def get_rule_class(self):
        return self._rule_class

    def get_details(self):
        return self._details


@unittest.skipUnless(HAS_CORE_SUPPORT and HAS_USER_RULES, "Requires Caster core experimental functions and user rules")
class TestAntigravityContextResolution(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not HAS_USER_RULES:
            return

        maker = MappingRuleMaker(MockTransformerRunner(), MockSmrConfigurer())

        # Load Antigravity Standalone Rule
        rule_anti_cls, details_anti = get_antigravity_standalone_rule()
        cls.grammar_anti = maker.create_non_ccr_grammar(ManagedRuleMock(rule_anti_cls, details_anti))
        cls.grammar_anti.load()

        # Load Antigravity IDE Rule
        rule_ide_cls, details_ide = get_antigravity_ide_rule()
        cls.grammar_ide = maker.create_non_ccr_grammar(ManagedRuleMock(rule_ide_cls, details_ide))
        cls.grammar_ide.load()

        # Load VS Code Rule
        rule_vsc_cls, details_vsc = get_vscode_rule()
        cls.grammar_vsc = maker.create_non_ccr_grammar(ManagedRuleMock(rule_vsc_cls, details_vsc))
        cls.grammar_vsc.load()

        # Load standard Firefox Rule (which is disabled by default in rules.toml)
        rule_ff_cls, details_ff = get_firefox_rule()
        cls.grammar_ff = maker.create_non_ccr_grammar(ManagedRuleMock(rule_ff_cls, details_ff))
        cls.grammar_ff.load()

    def test_bare_process_resolution(self):
        """Verifies target_process='antigravity' resolves to Antigravity Standalone."""
        rules = get_active_contextual_rules(target_process="antigravity")
        self.assertIn("Antigravity Standalone", rules)
        self.assertNotIn("Antigravity IDE", rules)
        self.assertNotIn("CustomVSCode", rules)

    def test_exe_suffixed_process_resolution(self):
        """Verifies target_process='Antigravity.exe' resolves to Antigravity Standalone."""
        rules = get_active_contextual_rules(target_process="Antigravity.exe")
        self.assertIn("Antigravity Standalone", rules)
        self.assertNotIn("Antigravity IDE", rules)
        self.assertNotIn("CustomVSCode", rules)

    def test_ide_isolation_no_standalone_leak(self):
        """
        Verifies target_process='antigravity ide' activates Antigravity IDE
        without false-positive cross-contamination from Antigravity Standalone.
        """
        rules = get_active_contextual_rules(target_process="antigravity ide", target_title="Antigravity IDE")
        self.assertIn("Antigravity IDE", rules)
        self.assertIn("CustomVSCode", rules)
        self.assertNotIn("Antigravity Standalone", rules)

    def test_universal_precision_matcher_unit(self):
        """Verifies precision executable matching across various prefix/stem boundaries."""
        # Stem and suffix matching
        self.assertTrue(_match_executable_precision(["antigravity", "antigravity.exe"], ["antigravity"]))
        self.assertTrue(_match_executable_precision(["antigravity", "antigravity.exe"], ["Antigravity.exe"]))
        self.assertTrue(_match_executable_precision(["antigravity.exe"], ["antigravity", "antigravity.exe"]))

        # Prefix boundary protection (e.g. 'antigravity ide' must NOT match 'antigravity')
        self.assertFalse(_match_executable_precision(["antigravity ide", "antigravity ide.exe"], ["antigravity", "antigravity.exe"]))
        self.assertTrue(_match_executable_precision(["antigravity ide", "antigravity ide.exe"], ["Antigravity IDE"]))

        # Notepad vs Notepad++ boundary protection
        self.assertFalse(_match_executable_precision(["notepad++", "notepad++.exe"], ["notepad"]))
        self.assertTrue(_match_executable_precision(["notepad", "notepad.exe"], ["notepad"]))

    def test_rules_toml_inactive_rule_filtering(self):
        """
        Verifies that FirefoxRule (which is registered in [whitelisted] in rules.toml
        but omitted from _enabled_ordered) is filtered out even when focusing 'firefox'.
        """
        rules_ff = get_active_contextual_rules(target_process="firefox", target_title="Mozilla Firefox")
        # FirefoxRule ('fire fox') is disabled in rules.toml and must not be present
        self.assertNotIn("fire fox", rules_ff)

    def test_disabled_dragonfly_rule_filtering(self):
        """Verifies that if rule.active is False, the rule is not reported."""
        mock_rule = MagicMock()
        mock_rule.active = False
        mock_rule.__class__.__name__ = "AntigravityAppRule"
        self.assertFalse(_is_rule_enabled_in_config(mock_rule, {"AntigravityAppRule"}, {"AntigravityAppRule"}))

    def test_adce_context_resolution_when_unspecified(self):
        """Verifies that when target_process is omitted, context is resolved via ADCE tracker."""
        mock_tracker = MagicMock()
        mock_tracker.is_connected.return_value = True
        mock_tracker.get_current_context.return_value = {
            "is_connected": True,
            "process_name": "antigravity.exe",
            "window_title": "Antigravity",
            "semantic_zone": "",
            "active_file": "",
        }
        with patch("castervoice.asynch.hud_support.get_focus_tracker", return_value=mock_tracker):
            rules = get_active_contextual_rules()
            self.assertIn("Antigravity Standalone", rules)
            self.assertNotIn("Antigravity IDE", rules)

    def test_ccr_display_name_resolution_no_vscodium_leak(self):
        """
        Verifies that CustomVSCodeCcrRule RepeatRule displays as 'CustomVSCode CCR'
        and NEVER leaks 'Vscodium' (or 'VSCodium') to the HUD when focusing Antigravity IDE.
        """
        from dragonfly import CompoundRule, AppContext
        from castervoice.asynch.hud_support import _format_rcn_display_name

        class DummyRepeatRule(CompoundRule):
            spec = "test"
            def _process_recognition(self, node, extras): pass

        self.assertEqual(_format_rcn_display_name("CustomVSCodeCcrRule"), "CustomVSCode CCR")
        self.assertEqual(_format_rcn_display_name("FirefoxCcrRule"), "Firefox CCR")
        self.assertEqual(_format_rcn_display_name("PowershellCCRRule"), "Powershell CCR")

        # Create mock CCR RepeatRule for VS Code
        ctx = AppContext(executable=["VSCodium", "code", "Windsurf", "Antigravity IDE"], title=["Antigravity IDE"])
        grammar = Grammar(name="test-ccr-vscode", context=ctx)
        rule = DummyRepeatRule(name="Repeater99")
        rule.ccr_rule_class_name = "CustomVSCodeCcrRule"
        rule.ccr_display_name = "CustomVSCode CCR"
        grammar.add_rule(rule)
        grammar.load()

        rules = get_active_contextual_rules(target_process="antigravity ide", target_title="Antigravity IDE")
        self.assertIn("CustomVSCode CCR", rules)
        self.assertNotIn("Vscodium", rules)
        self.assertNotIn("VSCodium", rules)

    def test_ccr_firefox_display_name_resolution(self):
        """
        Verifies that FirefoxCcrRule RepeatRule displays as 'Firefox CCR'
        and does NOT masquerade as 'Firefox' (which caused false belief that FirefoxRule was enabled).
        """
        from dragonfly import CompoundRule, AppContext

        class DummyRepeatRule(CompoundRule):
            spec = "test"
            def _process_recognition(self, node, extras): pass

        ctx = AppContext(executable=["firefox", "waterfox"], title=["Firefox"])
        grammar = Grammar(name="test-ccr-firefox", context=ctx)
        rule = DummyRepeatRule(name="Repeater100")
        rule.ccr_rule_class_name = "FirefoxCcrRule"
        rule.ccr_display_name = "Firefox CCR"
        grammar.add_rule(rule)
        grammar.load()

        rules = get_active_contextual_rules(target_process="firefox", target_title="Firefox")
        self.assertIn("Firefox CCR", rules)
        # Should not display the generic capitalized executable 'Firefox'
        self.assertNotIn("Firefox", rules)
        self.assertNotIn("fire fox", rules)


if __name__ == "__main__":
    unittest.main()
