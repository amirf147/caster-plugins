"""
End-to-end integration test verifying focus transition sequences between
Editor Buffer, Integrated Terminal, and External Applications.

Guarded by ADCE availability: runs when ADCE support and user rules are present,
and skips gracefully if ADCE is not configured.
"""

import sys
import unittest

from dragonfly import Grammar, get_current_engine
from castervoice.lib.context import AppContext
from castervoice.lib.ctrl.mgr.rule_maker.mapping_rule_maker import MappingRuleMaker
try:
    from castervoice.asynch.hud_support import (
        _on_adce_context_changed,
        _on_window_focus_changed,
        get_active_contextual_rules,
    )
    HAS_CORE_SUPPORT = True
except ImportError:
    HAS_CORE_SUPPORT = False


try:
    from adce import adce, is_ide_terminal_focused
    from caster_user_content.rules.apps.vscode.ide_terminal import IDETerminalRule, get_rule as get_ide_terminal_rule
    from caster_user_content.rules.apps.vscode.antigravity_ide import AntigravityIDERule, get_rule as get_antigravity_rule
    from caster_user_content.rules.apps.vscode.vscode import CustomVSCodeRule, get_rule as get_vscode_rule
    HAS_ADCE_INTEGRATION = True
except ImportError:
    HAS_ADCE_INTEGRATION = False


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


@unittest.skipUnless(HAS_CORE_SUPPORT and HAS_ADCE_INTEGRATION, "ADCE support, core functions, and IDE rules not present in environment")
class TestFocusTransitionSequence(unittest.TestCase):


    @classmethod
    def setUpClass(cls):
        if not HAS_ADCE_INTEGRATION:
            return

        # Stop background polling threads during test execution to prevent race conditions with live daemon
        from adce import adce
        adce.stop()

        maker = MappingRuleMaker(MockTransformerRunner(), MockSmrConfigurer())

        rule_term_cls, details_term = get_ide_terminal_rule()
        grammar_term = maker.create_non_ccr_grammar(ManagedRuleMock(rule_term_cls, details_term))
        grammar_term.load()

        rule_anti_cls, details_anti = get_antigravity_rule()
        grammar_anti = maker.create_non_ccr_grammar(ManagedRuleMock(rule_anti_cls, details_anti))
        grammar_anti.load()

        rule_vsc_cls, details_vsc = get_vscode_rule()
        grammar_vsc = maker.create_non_ccr_grammar(ManagedRuleMock(rule_vsc_cls, details_vsc))
        grammar_vsc.load()

    def _simulate_adce_focus(self, proc, title, zone, file="hud_support.py", connected=True):
        adce._current_process = (proc or "").lower()
        adce._current_title = title or ""
        adce._current_zone = zone or ""
        adce._active_file = file or ""
        adce._is_connected = connected
        _on_adce_context_changed(
            process_name=proc,
            window_title=title,
            semantic_zone=zone,
            active_file=file,
            is_connected=connected,
        )

    def test_complete_focus_sequence(self):
        proc = "antigravity ide"
        title = "hud_support.py - Caster - Antigravity IDE"

        # Step 1: User is focused in the Editor Buffer
        self._simulate_adce_focus(proc, title, "editor_buffer", "hud_support.py", True)
        rules_step1 = get_active_contextual_rules(target_process=proc, target_title=title)
        self.assertIn("Antigravity IDE", rules_step1)
        self.assertIn("CustomVSCode", rules_step1)
        self.assertNotIn("IDETerminal", rules_step1)

        # Step 2: User clicks into the Integrated Terminal (0-lag transition)
        self._simulate_adce_focus(proc, title, "terminal", "hud_support.py", True)
        rules_step2 = get_active_contextual_rules(target_process=proc, target_title=title)
        self.assertIn("Antigravity IDE", rules_step2)
        self.assertIn("CustomVSCode", rules_step2)
        self.assertIn("IDETerminal", rules_step2)

        # Step 3: User clicks away from terminal back into Editor Buffer (0-lag deactivation)
        self._simulate_adce_focus(proc, title, "editor_buffer", "hud_support.py", True)
        rules_step3 = get_active_contextual_rules(target_process=proc, target_title=title)
        self.assertIn("Antigravity IDE", rules_step3)
        self.assertIn("CustomVSCode", rules_step3)
        self.assertNotIn("IDETerminal", rules_step3)

        # Step 4: User clicks away from IDE to Chrome
        self._simulate_adce_focus("chrome", "Google Chrome", "", "", True)
        _on_window_focus_changed("chrome", "Google Chrome")
        rules_step4 = get_active_contextual_rules(target_process="chrome", target_title="Google Chrome")
        self.assertNotIn("IDETerminal", rules_step4)
        self.assertNotIn("Antigravity IDE", rules_step4)
        self.assertNotIn("CustomVSCode", rules_step4)

    def test_adce_disconnected_fallback(self):
        """Verifies that when ADCE is disconnected, HUD rules fallback safely without throwing."""
        self._simulate_adce_focus("", "", "", "", False)
        rules_offline = get_active_contextual_rules(target_process="notepad", target_title="Untitled - Notepad")
        self.assertIsInstance(rules_offline, list)
        self.assertNotIn("IDETerminal", rules_offline)


if __name__ == "__main__":
    unittest.main()
