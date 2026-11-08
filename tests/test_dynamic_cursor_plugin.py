# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Automated unit tests for Dynamic Cursor Plugin.

Verifies deterministic context-to-badge resolution, bridge client framing,
state deduplication, plugin lifecycle, and manifest options schema.
"""

import json
import struct
import unittest
from unittest.mock import MagicMock

from plugins.dynamic_cursor.bridge import DynamicCursorBridgeClient
from plugins.dynamic_cursor.context_mapper import (
    BROWSER_PROCESS_NAMES,
    IDE_PROCESS_NAMES,
    TERMINAL_PROCESS_NAMES,
    WRITING_PROCESS_NAMES,
    resolve_context_badge,
)
from plugins.dynamic_cursor.plugin import DynamicCursorPlugin
from plugins.dynamic_cursor.printer_handler import DynamicCursorPrintHandler
from plugins.plugin_manager.core.options import OptionType
from plugins.plugin_manager.core.scanner import PluginScanner


class TestContextMapper(unittest.TestCase):
    """Verifies pure context-to-badge resolution across all classification rules."""

    def test_stage1_terminal_zones(self):
        for zone in ("terminal", "integratedterminal", "integrated_terminal", "IntegratedTerminal", "2"):
            self.assertEqual(
                resolve_context_badge("unknown_app", semantic_zone=zone),
                "terminal_prompt",
                f"Failed for zone {zone}",
            )

    def test_stage1_web_zones(self):
        for zone in ("webdocument", "web_document", "WebDocument", "documentcontent", "addressbar", "5", "6"):
            self.assertEqual(
                resolve_context_badge("code", semantic_zone=zone),
                "web_globe",
                f"Failed for zone {zone}",
            )

    def test_stage1_writing_zones(self):
        for zone in ("chatprompt", "chat_prompt", "chatconversation", "chatassistant", "gitcommitbox", "3", "11", "18"):
            self.assertEqual(
                resolve_context_badge("code", semantic_zone=zone),
                "doc_writing",
                f"Failed for zone {zone}",
            )

    def test_stage1_editor_buffer_differentiation(self):
        for zone in ("editorbuffer", "editor_buffer", "editorcodebuffer", "1"):
            # Writing apps get doc_writing
            self.assertEqual(resolve_context_badge("notepad", semantic_zone=zone), "doc_writing")
            self.assertEqual(resolve_context_badge("obsidian.exe", semantic_zone=zone), "doc_writing")
            # Browsers get web_globe
            self.assertEqual(resolve_context_badge("waterfox", semantic_zone=zone), "web_globe")
            self.assertEqual(resolve_context_badge("chrome.exe", semantic_zone=zone), "web_globe")
            # IDEs get code_brackets
            self.assertEqual(resolve_context_badge("code", semantic_zone=zone), "code_brackets")
            self.assertEqual(resolve_context_badge("antigravity.exe", semantic_zone=zone), "code_brackets")

    def test_stage2_browser_fallbacks(self):
        for browser in BROWSER_PROCESS_NAMES:
            self.assertEqual(resolve_context_badge(browser, semantic_zone=""), "web_globe")
            self.assertEqual(resolve_context_badge(f"{browser}.exe", semantic_zone="--"), "web_globe")
            self.assertEqual(resolve_context_badge(browser, semantic_zone="tabbar"), "web_globe")

    def test_stage2_terminal_fallbacks(self):
        for term in TERMINAL_PROCESS_NAMES:
            self.assertEqual(resolve_context_badge(term, semantic_zone=""), "terminal_prompt")
            self.assertEqual(resolve_context_badge(f"{term}.exe", semantic_zone="unknown"), "terminal_prompt")

    def test_stage2_ide_fallbacks(self):
        for ide in IDE_PROCESS_NAMES:
            self.assertEqual(resolve_context_badge(ide, semantic_zone=""), "code_brackets")
            self.assertEqual(resolve_context_badge(f"{ide}.exe", semantic_zone="sidebar_explorer"), "code_brackets")

    def test_stage2_writing_fallbacks(self):
        for writing in WRITING_PROCESS_NAMES:
            self.assertEqual(resolve_context_badge(writing, semantic_zone=""), "doc_writing")
            self.assertEqual(resolve_context_badge(f"{writing}.exe", semantic_zone=""), "doc_writing")

    def test_unclassified_process_returns_none(self):
        self.assertIsNone(resolve_context_badge("calc.exe", semantic_zone=""))
        self.assertIsNone(resolve_context_badge("explorer.exe", semantic_zone=""))
        self.assertIsNone(resolve_context_badge("", semantic_zone=""))
        self.assertIsNone(resolve_context_badge(None, semantic_zone=None))


class TestDynamicCursorBridgeClient(unittest.TestCase):
    """Verifies bridge framing, layer isolation, and state deduplication."""

    def setUp(self):
        self.bridge = DynamicCursorBridgeClient(
            pipe_name="test_cursor_pipe",
            enable_mic_tint=True,
            enable_context_badges=True,
            listening_tint="#44FF66",
            sleeping_tint="#FF5555",
            muted_tint="#888888",
        )

    def test_encode_frame_structure(self):
        payload = {"op": "upsert", "layer_id": "test", "priority": 50}
        encoded = DynamicCursorBridgeClient.encode_frame(payload)

        self.assertGreaterEqual(len(encoded), 4)
        prefix_len = struct.unpack("<I", encoded[:4])[0]
        json_bytes = encoded[4:]
        self.assertEqual(prefix_len, len(json_bytes))

        decoded = json.loads(json_bytes.decode("utf-8"))
        self.assertEqual(decoded["op"], "upsert")
        self.assertEqual(decoded["layer_id"], "test")
        self.assertEqual(decoded["priority"], 50)

    def test_update_mic_layer_upsert_and_deduplication(self):
        self.assertEqual(self.bridge._queue.qsize(), 0)

        # Awake state
        self.bridge.update_mic_layer("on")
        self.assertEqual(self.bridge._queue.qsize(), 1)
        item1 = self.bridge._queue.get_nowait()
        self.assertEqual(item1["op"], "upsert")
        self.assertEqual(item1["layer_id"], "caster_mic")
        self.assertEqual(item1["priority"], 80)
        self.assertEqual(item1["tint_rgba"], "#44FF66")

        # Deduplication: calling again does not re-enqueue
        self.bridge.update_mic_layer("on")
        self.assertEqual(self.bridge._queue.qsize(), 0)

        # Sleeping state
        self.bridge.update_mic_layer("sleeping")
        self.assertEqual(self.bridge._queue.qsize(), 1)
        item2 = self.bridge._queue.get_nowait()
        self.assertEqual(item2["tint_rgba"], "#FF5555")

        # Muted / off state
        self.bridge.update_mic_layer("off")
        self.assertEqual(self.bridge._queue.qsize(), 1)
        item3 = self.bridge._queue.get_nowait()
        self.assertEqual(item3["tint_rgba"], "#888888")
        self.assertEqual(item3["badge_id"], "mic_off")

    def test_update_mic_layer_disabled(self):
        bridge = DynamicCursorBridgeClient(enable_mic_tint=False)
        bridge.update_mic_layer("on")
        self.assertEqual(bridge._queue.qsize(), 1)
        item = bridge._queue.get_nowait()
        self.assertEqual(item, {"op": "remove", "layer_id": "caster_mic"})

    def test_update_context_layer_upsert_and_deduplication(self):
        self.assertEqual(self.bridge._queue.qsize(), 0)

        self.bridge.update_context_layer("code_brackets")
        self.assertEqual(self.bridge._queue.qsize(), 1)
        item1 = self.bridge._queue.get_nowait()
        self.assertEqual(item1["op"], "upsert")
        self.assertEqual(item1["layer_id"], "adce_context")
        self.assertEqual(item1["priority"], 30)
        self.assertEqual(item1["badge_id"], "code_brackets")

        # Deduplication: same badge does not re-enqueue
        self.bridge.update_context_layer("code_brackets")
        self.assertEqual(self.bridge._queue.qsize(), 0)

        # Clear / removal via None
        self.bridge.update_context_layer(None)
        self.assertEqual(self.bridge._queue.qsize(), 1)
        item2 = self.bridge._queue.get_nowait()
        self.assertEqual(item2, {"op": "remove", "layer_id": "adce_context"})

    def test_update_context_layer_disabled(self):
        bridge = DynamicCursorBridgeClient(enable_context_badges=False)
        bridge.update_context_layer("web_globe")
        self.assertEqual(bridge._queue.qsize(), 1)
        item = bridge._queue.get_nowait()
        self.assertEqual(item, {"op": "remove", "layer_id": "adce_context"})

    def test_stop_enqueues_clear(self):
        self.bridge.stop()
        self.assertGreaterEqual(self.bridge._queue.qsize(), 1)
        item = self.bridge._queue.get_nowait()
        self.assertEqual(item, {"op": "clear"})


class TestDynamicCursorPluginLifecycle(unittest.TestCase):
    """Verifies plugin initialization, event routing, and teardown."""

    def test_plugin_initialize_and_event_routing(self):
        plugin = DynamicCursorPlugin()
        mock_nexus = MagicMock()
        mock_nexus.engine_modes_manager.get_mic_mode.return_value = "on"

        config = {
            "pipe_name": "test_pipe",
            "autostart_daemon": False,
            "enable_mic_tint": True,
            "enable_context_badges": True,
            "listening_tint": "#00FF00",
            "sleeping_tint": "#FF0000",
        }

        plugin.initialize(mock_nexus, config)
        self.assertIsNotNone(plugin._bridge)
        self.assertEqual(plugin._bridge._listening_tint, "#00FF00")
        self.assertEqual(plugin._bridge._sleeping_tint, "#FF0000")

        # Engine modes listener registration verified
        mock_nexus.engine_modes_manager.add_mic_listener.assert_called_once_with(
            plugin._on_mic_mode_changed
        )

        # Trigger mic mode transition
        plugin._on_mic_mode_changed("sleeping")
        self.assertEqual(plugin._bridge._last_sent_mic_payload["tint_rgba"], "#FF0000")

        # Trigger ADCE context transition
        plugin._on_adce_context_changed(
            process_name="waterfox",
            semantic_zone="WebDocument",
            is_connected=True,
        )
        self.assertEqual(plugin._bridge._last_sent_badge_id, "web_globe")

        # ADCE disconnect cleans context badge
        plugin._on_adce_context_changed(
            process_name="notepad",
            semantic_zone="",
            is_connected=False,
        )
        self.assertEqual(plugin._bridge._last_sent_badge_id, "doc_writing")

        plugin.stop()
        self.assertFalse(plugin._running)

    def test_printer_handler_dispatches_mic_state(self):
        mock_bridge = MagicMock()
        handler = DynamicCursorPrintHandler(bridge=mock_bridge)

        handler.handle_message(["@ Caster: Microphone is sleeping"])
        mock_bridge.update_mic_layer.assert_called_with("sleeping")

        handler.handle_message(["@ Caster: Microphone is on"])
        mock_bridge.update_mic_layer.assert_called_with("on")

        handler.handle_message(["@ Microphone is off"])
        mock_bridge.update_mic_layer.assert_called_with("off")


class TestPluginScannerMetadata(unittest.TestCase):
    """Verifies PluginScanner discovers dynamic_cursor and extracts schema options."""

    def test_scanner_extracts_dynamic_cursor_options(self):
        scanner = PluginScanner()
        records = scanner.scan_all()
        self.assertIn("dynamic_cursor", records)

        plugin_record = records["dynamic_cursor"]
        self.assertEqual(plugin_record.metadata.name, "dynamic_cursor")
        self.assertEqual(plugin_record.metadata.version, "1.0.0")

        options = plugin_record.metadata.options
        self.assertIn("pipe_name", options)
        self.assertIn("autostart_daemon", options)
        self.assertIn("enable_mic_tint", options)
        self.assertIn("enable_context_badges", options)
        self.assertIn("listening_tint", options)
        self.assertIn("sleeping_tint", options)
        self.assertIn("muted_tint", options)

        self.assertEqual(options["pipe_name"].option_type, OptionType.STRING)
        self.assertEqual(options["pipe_name"].default, "dynamic_cursor")

        self.assertEqual(options["autostart_daemon"].option_type, OptionType.BOOL)
        self.assertTrue(options["autostart_daemon"].default)

        self.assertEqual(options["enable_mic_tint"].option_type, OptionType.BOOL)
        self.assertTrue(options["enable_mic_tint"].default)

        self.assertEqual(options["enable_context_badges"].option_type, OptionType.BOOL)
        self.assertTrue(options["enable_context_badges"].default)

        self.assertEqual(options["listening_tint"].option_type, OptionType.STRING)
        self.assertEqual(options["listening_tint"].default, "#44FF66")


if __name__ == "__main__":
    unittest.main()
