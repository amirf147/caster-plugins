# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Unit and integration test suite for Plugin Manager runtime and Dragonfly voice rules.
"""

import unittest
from unittest.mock import MagicMock, patch

from plugins.plugin_manager import runner_bridge
from plugins.plugin_manager.plugin import PluginManagerPlugin
from plugins.plugin_manager.rules import PluginManagerRule, get_rule


class TestPluginManagerRuntime(unittest.TestCase):
    """Tests for voice command definitions and runtime lifecycle hooks."""

    def setUp(self):
        # Reset any global process handles between test cases
        runner_bridge._active_process = None

    def tearDown(self):
        runner_bridge._active_process = None

    def test_rule_specs_deterministic_and_unbranched(self):
        """Verifies that voice commands are clean, deterministic, and free of complex syntax branches."""
        mapping = PluginManagerRule.mapping

        expected_commands = {
            "plugin manager",
            "plugin manager refresh",
            "plugin manager close",
        }
        self.assertEqual(set(mapping.keys()), expected_commands)

        for cmd in mapping.keys():
            # Invariant: No optional branches or parentheses
            self.assertNotIn("(", cmd)
            self.assertNotIn(")", cmd)
            self.assertNotIn("[", cmd)
            self.assertNotIn("]", cmd)
            self.assertNotIn("|", cmd)
            self.assertTrue(cmd.startswith("plugin manager"))

    def test_get_rule_export_contract(self):
        """Verifies that get_rule returns valid (RuleClass, RuleDetails) tuple."""
        rule_class, details = get_rule()
        self.assertEqual(rule_class, PluginManagerRule)
        self.assertEqual(details.name, "plugin manager")

    def test_plugin_lifecycle_exports_rule(self):
        """Verifies that PluginManagerPlugin.get_rules returns companion rule."""
        plugin = PluginManagerPlugin()
        rules = plugin.get_rules()

        self.assertEqual(len(rules), 1)
        rule_class, details = rules[0]
        self.assertEqual(rule_class, PluginManagerRule)
        self.assertEqual(details.name, "plugin manager")

    @patch("subprocess.Popen")
    def test_process_bridge_dispatch_and_single_instance(self, mock_popen):
        """Verifies non-blocking subprocess spawning and single-instance process reuse."""
        fake_process = MagicMock()
        fake_process.poll.return_value = None  # Process is alive
        fake_process.pid = 12345
        mock_popen.return_value = fake_process

        # 1. Initial launch
        proc1 = runner_bridge.open_manager_process()
        self.assertEqual(proc1, fake_process)
        mock_popen.assert_called_once()

        # 2. Second launch attempt (should reuse active instance without spawning new subprocess)
        with patch.object(runner_bridge, "bring_window_to_front", return_value=True) as mock_focus:
            proc2 = runner_bridge.open_manager_process()
            self.assertEqual(proc2, fake_process)
            mock_popen.assert_called_once()  # Call count remains 1
            mock_focus.assert_called_once()

        # 3. Close process
        closed = runner_bridge.close_manager()
        self.assertTrue(closed)
        fake_process.terminate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
