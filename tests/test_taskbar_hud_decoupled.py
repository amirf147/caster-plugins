# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Integration and unit tests verifying decoupling of Caster Core, ADCE plugin,
and Taskbar HUD plugin.
"""

import unittest
from unittest.mock import MagicMock

from castervoice.lib import control, printer
from castervoice.lib.ctrl.mgr.engine_manager import EngineModesManager

try:
    from taskbar_hud import (
        TaskbarHudBridgeClient,
        get_taskbar_hud_bridge,
        TaskbarHudPrintHandler,
        TaskbarHudPlugin,
    )
    from adce import adce, add_context_listener, remove_context_listener
    HAS_PLUGINS = True
except (ImportError, ModuleNotFoundError):
    HAS_PLUGINS = False


@unittest.skipUnless(HAS_PLUGINS, "Plugins not present in test environment")
class TestTaskbarHudDecoupledArchitecture(unittest.TestCase):

    def setUp(self):
        self.bridge = get_taskbar_hud_bridge()

    def test_taskbar_hud_bridge_standalone(self):
        """Verifies TaskbarHudBridgeClient queues packets without requiring ADCE."""
        initial_qsize = self.bridge._queue.qsize()
        self.bridge.send_update(command="Test Command", status="recognized", mic_state="on")
        self.assertGreaterEqual(self.bridge._queue.qsize(), initial_qsize)
        self.assertEqual(self.bridge._cached_command, "Test Command")
        self.assertEqual(self.bridge._cached_status, "recognized")
        self.assertEqual(self.bridge._cached_mic_state, "on")

    def test_mic_mode_changed_updates_bridge(self):
        """Verifies EngineModesManager mic state changes update the taskbar bridge."""
        plugin = TaskbarHudPlugin()
        plugin._bridge = self.bridge
        plugin._on_mic_mode_changed("sleeping")
        self.assertEqual(self.bridge._cached_mic_state, "sleeping")
        self.assertEqual(self.bridge._cached_command, "Sleeping")
        self.assertEqual(self.bridge._cached_status, "sleeping")

        plugin._on_mic_mode_changed("on")
        self.assertEqual(self.bridge._cached_mic_state, "on")
        self.assertEqual(self.bridge._cached_command, "Ready")
        self.assertEqual(self.bridge._cached_status, "idle")

    def test_adce_context_listeners(self):
        """Verifies registering and firing ADCE context listeners."""
        events = []

        def listener(process_name, window_title, semantic_zone, active_file, is_connected):
            events.append({
                "process": process_name,
                "title": window_title,
                "zone": semantic_zone,
                "file": active_file,
                "connected": is_connected,
            })

        add_context_listener(listener)
        try:
            # Simulate snapshot ingestion
            test_snapshot = {
                "window": {"process_name": "test_app", "title": "Test Window"},
                "focus": {"semantic_zone": "terminal"},
                "ide_context": {"active_tab": {"title": "main.py"}},
            }
            adce._ingest_snapshot(test_snapshot)

            self.assertTrue(any(e["process"] == "test_app" and e["zone"] == "terminal" for e in events))
        finally:
            remove_context_listener(listener)

    def test_taskbar_hud_plugin_lifecycle(self):
        """Verifies TaskbarHudPlugin initializes, starts, and stops cleanly."""
        plugin = TaskbarHudPlugin()
        plugin.initialize(MagicMock(), {"pipe_name": "TestPipe"})
        self.assertEqual(plugin.name, "taskbar_hud")
        plugin.start()
        self.assertTrue(plugin.is_running)
        plugin.stop()
        self.assertFalse(plugin.is_running)


if __name__ == "__main__":
    unittest.main()
