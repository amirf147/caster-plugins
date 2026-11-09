# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Automated unit and integration tests for Unified Desktop Context Provider.

Verifies canonical semantic zone mapping, snapshot immutability, immediate listener
replay on subscription, disconnect fallback behavior preserving foreground window
details, and seamless integration with Dynamic Cursor and Taskbar HUD plugins.
"""

from dataclasses import FrozenInstanceError
import unittest
from unittest.mock import MagicMock, patch

from plugins.common.desktop_context import (
    DesktopContextProvider,
    ContextSnapshot,
    SemanticZone,
    canonicalize_zone,
    classify_process_zone,
)
from plugins.dynamic_cursor.plugin import DynamicCursorPlugin
from plugins.taskbar_hud.plugin import TaskbarHudPlugin


class TestCanonicalSemanticZoneMapping(unittest.TestCase):
    """Verifies deterministic mapping from raw ADCE strings and integer IDs to canonical zones."""

    def test_editor_zone_mappings(self):
        for raw in ("1", "editor", "editorbuffer", "editorcodebuffer", "codeeditor", "Editor_Buffer", "EDITORCODEBUFFER"):
            self.assertEqual(
                canonicalize_zone(raw),
                SemanticZone.EDITOR,
                f"Failed canonicalizing editor zone variant: {raw}",
            )

    def test_terminal_zone_mappings(self):
        for raw in ("2", "terminal", "integratedterminal", "integrated_terminal", "console", "shell", "TERMINAL"):
            self.assertEqual(
                canonicalize_zone(raw),
                SemanticZone.TERMINAL,
                f"Failed canonicalizing terminal zone variant: {raw}",
            )

    def test_document_and_writing_zone_mappings(self):
        for raw in ("3", "18", "document", "doc", "writing", "gitcommitbox", "git_commit_box", "notes"):
            self.assertEqual(
                canonicalize_zone(raw),
                SemanticZone.DOCUMENT,
                f"Failed canonicalizing document zone variant: {raw}",
            )

    def test_web_zone_mappings(self):
        for raw in ("5", "6", "web", "webdocument", "documentcontent", "addressbar", "browser", "Web_Document"):
            self.assertEqual(
                canonicalize_zone(raw),
                SemanticZone.WEB,
                f"Failed canonicalizing web zone variant: {raw}",
            )

    def test_chat_zone_mappings(self):
        for raw in ("11", "chat", "chatprompt", "chatconversation", "chatassistant", "assistant", "Chat_Prompt"):
            self.assertEqual(
                canonicalize_zone(raw),
                SemanticZone.CHAT,
                f"Failed canonicalizing chat zone variant: {raw}",
            )

    def test_unknown_and_invalid_zone_mappings(self):
        for raw in ("", None, "unknown", "--", "sidebar", "random_unmapped_zone"):
            self.assertEqual(
                canonicalize_zone(raw),
                SemanticZone.UNKNOWN,
                f"Failed mapping unknown zone: {raw}",
            )

    def test_classify_process_zone(self):
        self.assertEqual(classify_process_zone("code.exe"), SemanticZone.EDITOR)
        self.assertEqual(classify_process_zone("pwsh"), SemanticZone.TERMINAL)
        self.assertEqual(classify_process_zone("waterfox.exe"), SemanticZone.WEB)
        self.assertEqual(classify_process_zone("notepad"), SemanticZone.DOCUMENT)
        self.assertEqual(classify_process_zone("calc.exe"), SemanticZone.UNKNOWN)


class TestContextSnapshotImmutability(unittest.TestCase):
    """Verifies that ContextSnapshot instances are strictly immutable frozen dataclasses."""

    def test_snapshot_default_values(self):
        snap = ContextSnapshot()
        self.assertEqual(snap.hwnd, 0)
        self.assertEqual(snap.process_name, "")
        self.assertEqual(snap.window_title, "")
        self.assertEqual(snap.semantic_zone, SemanticZone.UNKNOWN)
        self.assertEqual(snap.active_file, "")
        self.assertEqual(snap.terminal_shell, "")
        self.assertFalse(snap.is_adce_connected)

    def test_snapshot_reassignment_raises_frozen_error(self):
        snap = ContextSnapshot(
            hwnd=1001,
            process_name="code",
            window_title="main.py - VSCode",
            semantic_zone=SemanticZone.EDITOR,
            active_file="main.py",
            terminal_shell="",
            is_adce_connected=True,
        )
        with self.assertRaises(FrozenInstanceError):
            snap.process_name = "notepad"
        with self.assertRaises(FrozenInstanceError):
            snap.hwnd = 2002
        with self.assertRaises(FrozenInstanceError):
            snap.is_adce_connected = False


class TestDesktopContextProviderLifecycle(unittest.TestCase):
    """Verifies singleton provider subscriptions, replay caching, and disconnect behavior."""

    def setUp(self):
        DesktopContextProvider._reset_for_testing()
        self.provider = DesktopContextProvider.get_instance()

    def tearDown(self):
        DesktopContextProvider._reset_for_testing()

    def test_listener_immediate_replay_on_subscription(self):
        # Update baseline state in provider
        self.provider.update_adce_context(
            semantic_zone="terminal",
            active_file="",
            terminal_shell="pwsh.exe",
            is_connected=True,
            process_name="code",
            window_title="Terminal - Code",
        )

        received_snapshots = []

        def listener(snapshot: ContextSnapshot):
            received_snapshots.append(snapshot)

        # Immediate replay must invoke listener synchronously upon subscription
        self.provider.add_listener(listener)
        self.assertEqual(len(received_snapshots), 1)
        snap = received_snapshots[0]
        self.assertEqual(snap.process_name, "code")
        self.assertEqual(snap.semantic_zone, SemanticZone.TERMINAL)
        self.assertEqual(snap.terminal_shell, "pwsh.exe")
        self.assertTrue(snap.is_adce_connected)

        # Subsequent context updates must propagate to registered listener
        self.provider.update_adce_context(
            semantic_zone="editorcodebuffer",
            active_file="app.py",
            terminal_shell="",
            is_connected=True,
            process_name="code",
            window_title="app.py - Code",
        )
        self.assertEqual(len(received_snapshots), 2)
        self.assertEqual(received_snapshots[1].semantic_zone, SemanticZone.EDITOR)
        self.assertEqual(received_snapshots[1].active_file, "app.py")

        # Unregister listener
        self.provider.remove_listener(listener)
        self.provider.update_adce_context(
            semantic_zone="web",
            active_file="",
            terminal_shell="",
            is_connected=True,
            process_name="code",
            window_title="Docs - Code",
        )
        self.assertEqual(len(received_snapshots), 2)

    def test_disconnect_fallback_preserves_foreground_window(self):
        # Establish connected context
        self.provider.update_adce_context(
            semantic_zone="2",
            active_file="script.py",
            terminal_shell="pwsh.exe",
            is_connected=True,
            process_name="code",
            window_title="script.py - VSCode",
        )

        received = []
        self.provider.add_listener(lambda s: received.append(s))
        self.assertEqual(received[-1].is_adce_connected, True)

        # Trigger disconnect update
        self.provider.update_adce_context(is_connected=False)
        last_snap = received[-1]

        # Window identity preserved
        self.assertEqual(last_snap.process_name, "code")
        self.assertEqual(last_snap.window_title, "script.py - VSCode")
        self.assertFalse(last_snap.is_adce_connected)
        self.assertEqual(last_snap.active_file, "")
        self.assertEqual(last_snap.terminal_shell, "")

        # Fallback zone classified to editor for code rather than cleared to blank
        self.assertEqual(last_snap.semantic_zone, SemanticZone.EDITOR)


class TestPluginUnifiedContextIntegration(unittest.TestCase):
    """Verifies that Dynamic Cursor and Taskbar HUD plugins consume DesktopContextProvider."""

    def setUp(self):
        DesktopContextProvider._reset_for_testing()
        self.provider = DesktopContextProvider.get_instance()

    def tearDown(self):
        DesktopContextProvider._reset_for_testing()

    def test_dynamic_cursor_integration(self):
        plugin = DynamicCursorPlugin()
        mock_bridge = MagicMock()
        plugin._bridge = mock_bridge
        plugin._running = True

        # Simulate provider context transitions
        self.provider.update_adce_context(
            semantic_zone="terminal",
            active_file="",
            terminal_shell="cmd.exe",
            is_connected=True,
            process_name="code",
            window_title="cmd",
        )

        # Dynamic Cursor subscribes to DesktopContextProvider
        self.provider.add_listener(plugin._on_desktop_context_changed)

        # Immediate replay triggers update_context_layer
        mock_bridge.update_context_layer.assert_called_with("terminal_prompt")

        # Update to web zone in browser
        self.provider.update_adce_context(
            semantic_zone="webdocument",
            active_file="",
            terminal_shell="",
            is_connected=True,
            process_name="waterfox",
            window_title="Mozilla",
        )
        mock_bridge.update_context_layer.assert_called_with("web_globe")

        # Unregister on stop
        plugin.stop()
        self.assertNotIn(plugin._on_desktop_context_changed, self.provider._listeners)

    def test_taskbar_hud_integration(self):
        plugin = TaskbarHudPlugin()
        mock_bridge = MagicMock()
        mock_bridge._cached_rules = ""
        mock_bridge._cached_zone = ""
        plugin._bridge = mock_bridge
        plugin._running = True

        # Seed provider with active context
        self.provider.update_adce_context(
            semantic_zone="editorcodebuffer",
            active_file="main.py",
            terminal_shell="",
            is_connected=True,
            process_name="code",
            window_title="main.py - VSCode",
        )

        with patch("plugins.taskbar_hud.plugin.resolve_active_rules") as mock_resolve:
            mock_resolve.return_value = ["PythonRule", "VSCodeRule"]

            # Taskbar HUD subscribes to DesktopContextProvider
            self.provider.add_listener(plugin._on_desktop_context_changed)

            # Assert resolve_active_rules received hwnd and snapshot parameters
            mock_resolve.assert_called_with(
                process_name="code",
                window_title="main.py - VSCode",
                semantic_zone=SemanticZone.EDITOR,
                hwnd=0,
            )

            # Verify bridge was notified with active rules and zone
            mock_bridge.send_update.assert_called_with(
                adce_zone=SemanticZone.EDITOR,
                rules="PythonRule, VSCodeRule",
            )

        # Unregister on stop
        plugin.stop()
        self.assertNotIn(plugin._on_desktop_context_changed, self.provider._listeners)

    def test_adce_client_disconnect_preserves_window_details(self):
        from plugins.adce.client import AdceBridgeClient

        client = AdceBridgeClient.get_instance()
        client._current_process = "code"
        client._current_title = "test.py - Code"
        client._current_zone = "editor"
        client._is_connected = True

        notifications = []

        def listener(process_name, window_title, semantic_zone, active_file, is_connected, **kwargs):
            notifications.append({
                "proc": process_name,
                "title": window_title,
                "zone": semantic_zone,
                "connected": is_connected,
            })

        client.add_context_listener(listener)
        try:
            client._handle_disconnect()
            self.assertGreaterEqual(len(notifications), 1)
            last = notifications[-1]
            self.assertEqual(last["proc"], "code")
            self.assertEqual(last["title"], "test.py - Code")
            self.assertFalse(last["connected"])
        finally:
            client.remove_context_listener(listener)


if __name__ == "__main__":
    unittest.main()
