"""
Unit tests for Caster HUD UI Window, Dialogs, and Signal Bridge.
"""

import sys
import time
import unittest
from castervoice.lib.qt import QtWidgets, QtCore
from hud.ui.main_window import MainWindow
from hud.core.events import MicStateEvent, RecognitionEvent, DragModeEvent


class TestHudUI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance()
        if cls.app is None:
            cls.app = QtWidgets.QApplication(sys.argv)

    def test_main_window_lifecycle_and_dialogs(self):
        window = MainWindow()
        window.show()
        self.app.processEvents()

        # Test Drag Mode toggle
        window.toggle_drag_mode()
        self.app.processEvents()
        self.assertTrue(window.state.is_drag_mode)
        self.assertEqual(window.state.get_border_color(), "#f39c12")  # Amber

        # Test Mic State Sleeping while Drag Mode (Mic takes priority)
        window.dispatch_event(MicStateEvent(mode="sleeping"))
        self.app.processEvents()
        self.assertEqual(window.state.get_border_color(), "#e74c3c")  # Red

        # Test Exit Drag Mode
        window.toggle_drag_mode()
        self.app.processEvents()
        self.assertFalse(window.state.is_drag_mode)

        # Test Show Help Dialog
        window.show_help_dialog()
        self.app.processEvents()
        self.assertIsNotNone(window.help_dialog)
        self.assertTrue(window.help_dialog.isVisible())
        window.hide_help_dialog()
        self.app.processEvents()
        self.assertFalse(window.help_dialog.isVisible())

        # Test Show Rules Dialog
        sample_rules_json = '[{"name": "TestGrammar", "rules": [{"name": "TestRule", "specs": ["spec1::action1"]}]}]'
        window.show_rules_dialog(sample_rules_json)
        self.app.processEvents()
        self.assertIsNotNone(window.rules_dialog)
        self.assertTrue(window.rules_dialog.isVisible())
        window.hide_rules_dialog()
        self.app.processEvents()
        self.assertIsNone(window.rules_dialog)

        # Test Show Profile Dialog
        window.show_profile_dialog("save")
        self.app.processEvents()
        self.assertIsNotNone(window.profile_dialog)
        self.assertTrue(window.profile_dialog.isVisible())
        window.profile_dialog.close()
        self.app.processEvents()

        # Test Show Theme Customizer Dialog & Opacity
        window.set_opacity(0.85)
        self.app.processEvents()
        self.assertEqual(window.state.opacity, 0.85)

        window.set_background_opacity(0.60)
        self.app.processEvents()
        self.assertEqual(window.state.background_opacity, 0.60)

        window.set_text_opacity(0.80)
        self.app.processEvents()
        self.assertEqual(window.state.text_opacity, 0.80)

        window.show_theme_dialog()
        self.app.processEvents()
        self.assertIsNotNone(window.theme_dialog)
        self.assertTrue(window.theme_dialog.isVisible())
        self.assertGreaterEqual(window.theme_dialog.theme_combo.count(), 4)

        # Test dual sliders live interaction
        window.theme_dialog.bg_opacity_slider.setValue(50)
        self.app.processEvents()
        self.assertEqual(window.state.background_opacity, 0.50)

        window.theme_dialog.text_opacity_slider.setValue(70)
        self.app.processEvents()
        self.assertEqual(window.state.text_opacity, 0.70)

        # Test text alignment live interaction
        window.theme_dialog.align_right_radio.setChecked(True)
        self.app.processEvents()
        self.assertEqual(window.state.text_alignment, "right")
        self.assertEqual(window.log_widget._text_alignment, "right")

        window.theme_dialog.align_left_radio.setChecked(True)
        self.app.processEvents()
        self.assertEqual(window.state.text_alignment, "left")
        self.assertEqual(window.log_widget._text_alignment, "left")

        window.theme_dialog.close()
        self.app.processEvents()

        window.close()
        self.app.processEvents()

    def test_caster_rule_grammar_import(self):
        """Verify that caster_rule.py imports cleanly and builds rule details without NameError."""
        import castervoice.rules.core.utility_rules.caster_rule as cr
        rule_class, details = cr.get_rule()
        self.assertIsNotNone(rule_class)
        self.assertTrue(any("show caster hud" in k for k in rule_class.mapping))
        self.assertTrue(any("show caster rules" in k for k in rule_class.mapping))
        self.assertTrue(any("clear caster hud" in k for k in rule_class.mapping))
        self.assertTrue(any("restart" in k and "hud" in k for k in rule_class.mapping))


    def test_themed_hud_companion_rules(self):
        """Verify that themed_hud plugin companion rules provide all customized HUD commands."""
        import sys, os
        plugin_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "plugins", "themed_hud"))
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)
        import rules
        rule_class, details = rules.get_rule()
        self.assertIsNotNone(rule_class)
        self.assertIn("show caster [hud] help", rule_class.mapping)
        self.assertIn("caster hud [text] align <hud_alignment>", rule_class.mapping)
        self.assertIn("show caster [hud] (customize | themes | customizer)", rule_class.mapping)
        self.assertIn("[caster hud] (status | header | status bar) [toggle]", rule_class.mapping)
        self.assertIn("[caster hud] (rules strip | active rules [strip] | rules bar | active rules) [toggle]", rule_class.mapping)
        self.assertIn("[caster hud] (context strip | adce bar | adce) [toggle]", rule_class.mapping)


if __name__ == "__main__":
    unittest.main()
