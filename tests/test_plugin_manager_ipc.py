# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Unit tests for PluginManagerIpcServer and PluginManagerIpcClient loopback orchestration.
"""

import time
import unittest
from unittest.mock import MagicMock

from plugins.plugin_manager.core.ipc_client import PluginManagerIpcClient
from plugins.plugin_manager.core.ipc_server import PluginManagerIpcServer

TEST_PORT = 8399


class DummyLoadedPlugin:
    def __init__(self, name: str, is_running: bool = True):
        self.name = name
        self.is_running = is_running


class TestPluginManagerIpc(unittest.TestCase):
    def test_client_offline_behavior(self):
        # Client pointing to unused port
        client = PluginManagerIpcClient(port=8398, timeout_seconds=0.1)
        self.assertFalse(client.is_connected())
        self.assertEqual(client.get_running_plugins(), set())
        success, msg = client.load_plugin("some_plugin")
        self.assertFalse(success)
        self.assertIn("IPC load command failed", msg)

    def test_server_and_client_roundtrip(self):
        mock_pm = MagicMock()
        mock_pm.get_loaded_plugins.return_value = [
            DummyLoadedPlugin("themed_hud", True),
            DummyLoadedPlugin("taskbar_hud", False),
        ]
        mock_pm.load_plugin.return_value = (True, "Loaded themed_hud")
        mock_pm.unload_plugin.return_value = (True, "Unloaded themed_hud")
        mock_pm.reload_all.return_value = (True, "Reloaded all")

        server = PluginManagerIpcServer(port=TEST_PORT)
        server._get_caster_plugin_manager = lambda: mock_pm

        started = server.start()
        self.assertTrue(started)
        self.assertTrue(server.is_running)

        try:
            # Short sleep to guarantee server loop listening
            time.sleep(0.1)

            client = PluginManagerIpcClient(port=TEST_PORT, timeout_seconds=1.0)
            self.assertTrue(client.is_connected())

            # 1. Query running plugins
            running = client.get_running_plugins()
            self.assertEqual(running, {"themed_hud"})

            # 2. Dynamic load
            ok, msg = client.load_plugin("themed_hud")
            self.assertTrue(ok)
            self.assertEqual(msg, "Loaded themed_hud")
            mock_pm.load_plugin.assert_called_once_with("themed_hud")

            # 3. Dynamic unload
            ok, msg = client.unload_plugin("themed_hud")
            self.assertTrue(ok)
            self.assertEqual(msg, "Unloaded themed_hud")
            mock_pm.unload_plugin.assert_called_once_with("themed_hud")

            # 4. Reload all
            ok, msg = client.reload_all()
            self.assertTrue(ok)
            self.assertEqual(msg, "Reloaded all")
            mock_pm.reload_all.assert_called_once()

        finally:
            server.stop()
            self.assertFalse(server.is_running)

            # Verify client reports offline after server stop
            time.sleep(0.1)
            self.assertFalse(client.is_connected())


if __name__ == "__main__":
    unittest.main()
