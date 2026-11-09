# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Unit tests for shared NamedPipeTransport, framing abstractions,
and updated bridge clients and printer handlers.
"""

import json
import struct
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from plugins.common.named_pipe import (
    INVALID_HANDLE_VALUE,
    LengthPrefixedFraming,
    NamedPipeTransport,
    NdjsonFraming,
)
from plugins.dynamic_cursor.bridge import DynamicCursorBridgeClient
from plugins.dynamic_cursor.printer_handler import DynamicCursorPrintHandler
from plugins.taskbar_hud.bridge import TaskbarHudBridgeClient
from plugins.taskbar_hud.printer_handler import TaskbarHudPrintHandler


class TestFramingAbstractions(unittest.TestCase):
    """Verifies length-prefixed and NDJSON framing serialization and batching."""

    def test_length_prefixed_framing_dict(self):
        framing = LengthPrefixedFraming()
        payload = {"op": "upsert", "layer_id": "test", "priority": 50}
        encoded = framing.encode(payload)

        self.assertGreaterEqual(len(encoded), 4)
        prefix_len = struct.unpack("<I", encoded[:4])[0]
        json_bytes = encoded[4:]
        self.assertEqual(prefix_len, len(json_bytes))

        decoded = json.loads(json_bytes.decode("utf-8"))
        self.assertEqual(decoded["op"], "upsert")
        self.assertEqual(decoded["layer_id"], "test")
        self.assertEqual(decoded["priority"], 50)

    def test_length_prefixed_framing_bytes_and_string(self):
        framing = LengthPrefixedFraming()

        raw_str = "hello-pipe"
        encoded_str = framing.encode(raw_str)
        prefix_len = struct.unpack("<I", encoded_str[:4])[0]
        self.assertEqual(prefix_len, len(raw_str.encode("utf-8")))
        self.assertEqual(encoded_str[4:], raw_str.encode("utf-8"))

        raw_bytes = b"binary-data"
        encoded_bytes = framing.encode(raw_bytes)
        prefix_len = struct.unpack("<I", encoded_bytes[:4])[0]
        self.assertEqual(prefix_len, len(raw_bytes))
        self.assertEqual(encoded_bytes[4:], raw_bytes)

    def test_length_prefixed_batch_sequential(self):
        framing = LengthPrefixedFraming()
        items = [{"id": 1}, {"id": 2}]
        batch_bytes = framing.encode_batch(items)

        frame1 = framing.encode(items[0])
        frame2 = framing.encode(items[1])
        self.assertEqual(batch_bytes, frame1 + frame2)

    def test_ndjson_framing_dict(self):
        framing = NdjsonFraming()
        payload = {"command": "status", "status": "recognized"}
        encoded = framing.encode(payload)

        self.assertTrue(encoded.endswith(b"\n"))
        decoded = json.loads(encoded.decode("utf-8").strip())
        self.assertEqual(decoded["command"], "status")
        self.assertEqual(decoded["status"], "recognized")

    def test_ndjson_framing_string_and_bytes(self):
        framing = NdjsonFraming()

        # String without trailing newline
        encoded_str = framing.encode('{"key": 1}')
        self.assertEqual(encoded_str, b'{"key": 1}\n')

        # String with trailing newline
        encoded_str_nl = framing.encode('{"key": 2}\n')
        self.assertEqual(encoded_str_nl, b'{"key": 2}\n')

        # Raw bytes
        encoded_bytes = framing.encode(b'{"key": 3}')
        self.assertEqual(encoded_bytes, b'{"key": 3}\n')

    def test_ndjson_framing_batch(self):
        framing = NdjsonFraming()
        items = [{"count": 1}, {"count": 2}, {"count": 3}]
        batch_bytes = framing.encode_batch(items)

        lines = batch_bytes.decode("utf-8").strip().split("\n")
        self.assertEqual(len(lines), 3)
        self.assertEqual(json.loads(lines[0])["count"], 1)
        self.assertEqual(json.loads(lines[1])["count"], 2)
        self.assertEqual(json.loads(lines[2])["count"], 3)


class TestNamedPipeTransportLifecycle(unittest.TestCase):
    """Verifies transport bounded queueing, connection lifecycle, and state replay."""

    def test_bounded_drop_oldest_queue(self):
        transport = NamedPipeTransport(
            pipe_name="test_bounded",
            max_queue_size=3,
        )

        # Enqueue 5 items into queue of capacity 3
        for item in ["first", "second", "third", "fourth", "fifth"]:
            ok = transport.send(item)
            self.assertTrue(ok)

        self.assertEqual(transport.queue.qsize(), 3)
        # Oldest items ("first", "second") must be dropped
        remaining = [
            transport.queue.get_nowait(),
            transport.queue.get_nowait(),
            transport.queue.get_nowait(),
        ]
        self.assertEqual(remaining, ["third", "fourth", "fifth"])

    def test_flush_drains_queue(self):
        transport = NamedPipeTransport(pipe_name="test_flush")
        transport.send({"item": 1})
        transport.send({"item": 2})

        # Mock background drain
        def fake_drain():
            time.sleep(0.05)
            while not transport.queue.empty():
                transport.queue.get_nowait()

        t = threading.Thread(target=fake_drain)
        t.start()

        flushed = transport.flush(timeout=1.0)
        t.join()
        self.assertTrue(flushed)
        self.assertTrue(transport.queue.empty())

    def test_replay_on_connect_and_frame_writing(self):
        mock_pipe_handle = 99999
        writes = []
        flushes = []
        closes = []

        replay_payload = [{"layer": "base", "color": "#00FF00"}]

        transport = NamedPipeTransport(
            pipe_name="test_replay",
            framing=LengthPrefixedFraming(),
            replay_provider=lambda: replay_payload,
            min_backoff=0.01,
            max_backoff=0.05,
        )

        transport._open_pipe = MagicMock(return_value=mock_pipe_handle)

        def mock_write(handle, data):
            writes.append((handle, data))
            return True

        def mock_flush(handle):
            flushes.append(handle)
            return True

        def mock_close(handle):
            closes.append(handle)
            return True

        transport._write_bytes = mock_write
        transport._flush_handle = mock_flush
        transport._close_handle = mock_close

        transport.send({"layer": "overlay", "color": "#FF0000"})
        transport.start()

        # Allow sender loop to open pipe, replay state, and write pending packet
        deadline = time.time() + 1.0
        while len(writes) < 2 and time.time() < deadline:
            time.sleep(0.02)

        transport.stop()

        self.assertGreaterEqual(len(writes), 2)
        # First write is replay payload
        replay_encoded = LengthPrefixedFraming().encode(replay_payload[0])
        self.assertEqual(writes[0][1], replay_encoded)

        # Second write is enqueued payload
        overlay_encoded = LengthPrefixedFraming().encode({"layer": "overlay", "color": "#FF0000"})
        self.assertEqual(writes[1][1], overlay_encoded)

        self.assertIn(mock_pipe_handle, closes)

    def test_connection_retry_with_backoff(self):
        attempts = []
        mock_handle = 55555

        transport = NamedPipeTransport(
            pipe_name="test_backoff",
            min_backoff=0.02,
            max_backoff=0.08,
            backoff_factor=2.0,
        )

        def fake_open():
            attempts.append(time.time())
            if len(attempts) < 3:
                return INVALID_HANDLE_VALUE
            return mock_handle

        transport._open_pipe = fake_open
        transport._write_bytes = MagicMock(return_value=True)
        transport._flush_handle = MagicMock(return_value=True)
        transport._close_handle = MagicMock(return_value=True)

        transport.send({"item": "test"})
        transport.start()

        deadline = time.time() + 1.5
        while len(attempts) < 3 and time.time() < deadline:
            time.sleep(0.02)

        transport.stop()

        self.assertGreaterEqual(len(attempts), 3)
        self.assertTrue(transport._is_valid_handle(mock_handle))

    def test_on_stop_payload_dispatched_on_shutdown(self):
        mock_handle = 77777
        written_data = []

        transport = NamedPipeTransport(
            pipe_name="test_stop_payload",
            framing=LengthPrefixedFraming(),
            on_stop_payload={"op": "clear"},
            min_backoff=0.01,
        )

        transport._open_pipe = MagicMock(return_value=mock_handle)
        transport._write_bytes = lambda handle, data: written_data.append(data) or True
        transport._flush_handle = MagicMock(return_value=True)
        transport._close_handle = MagicMock(return_value=True)

        transport.send({"op": "init"})
        transport.start()

        # Wait for handle to open and initial item to be processed
        deadline = time.time() + 1.0
        while not written_data and time.time() < deadline:
            time.sleep(0.02)

        transport.stop()

        expected_clear = LengthPrefixedFraming().encode({"op": "clear"})
        self.assertIn(expected_clear, written_data)


class TestDynamicCursorBridgeRefactored(unittest.TestCase):
    """Verifies DynamicCursorBridgeClient integration with NamedPipeTransport."""

    def setUp(self):
        self.bridge = DynamicCursorBridgeClient(
            pipe_name="test_cursor_bridge",
            enable_mic_tint=True,
            enable_context_badges=True,
            listening_tint="#44FF66",
            sleeping_tint="#FF5555",
            muted_tint="#888888",
        )

    def test_public_methods_and_deduplication(self):
        self.assertEqual(self.bridge._queue.qsize(), 0)

        # 1. Update mic layer
        self.bridge.update_mic_layer("on")
        self.assertEqual(self.bridge._queue.qsize(), 1)
        item1 = self.bridge._queue.get_nowait()
        self.assertEqual(item1["layer_id"], "caster_mic")
        self.assertEqual(item1["tint_rgba"], "#44FF66")

        # Deduplication: identical mic state does not re-enqueue
        self.bridge.update_mic_layer("on")
        self.assertEqual(self.bridge._queue.qsize(), 0)

        # 2. Update context layer
        self.bridge.update_context_layer("code_editor")
        self.assertEqual(self.bridge._queue.qsize(), 1)
        item2 = self.bridge._queue.get_nowait()
        self.assertEqual(item2["layer_id"], "adce_context")
        self.assertEqual(item2["badge_id"], "code_editor")

        # Deduplication: identical badge does not re-enqueue
        self.bridge.update_context_layer("code_editor")
        self.assertEqual(self.bridge._queue.qsize(), 0)

        # 3. Clear layers method
        self.bridge.clear_layers()
        self.assertEqual(self.bridge._queue.qsize(), 1)
        item3 = self.bridge._queue.get_nowait()
        self.assertEqual(item3, {"op": "clear"})

    def test_state_replay_snapshot(self):
        self.bridge.update_mic_layer("sleeping")
        self.bridge.update_context_layer("browser_tab")

        replays = self.bridge._get_replay_payloads()
        self.assertEqual(len(replays), 2)
        self.assertEqual(replays[0]["tint_rgba"], "#FF5555")
        self.assertEqual(replays[1]["badge_id"], "browser_tab")


class TestTaskbarHudBridgeRefactored(unittest.TestCase):
    """Verifies TaskbarHudBridgeClient integration with NamedPipeTransport and NdjsonFraming."""

    def setUp(self):
        self.bridge = TaskbarHudBridgeClient(pipe_name="test_taskbar_bridge")

    def test_no_voice_command_parsing_in_bridge(self):
        # Bridge simply transmits voice commands without mutating mic state
        self.bridge.send_update(command="caster sleep", status="recognized")
        self.assertEqual(self.bridge._cached_command, "caster sleep")
        self.assertEqual(self.bridge._cached_status, "recognized")
        self.assertEqual(self.bridge._cached_mic_state, "on")

        packet = self.bridge._queue.get_nowait()
        self.assertEqual(packet["command"], "caster sleep")
        self.assertEqual(packet["status"], "recognized")
        self.assertEqual(packet["mic_state"], "on")

    def test_thread_safe_state_cache_and_convenience_methods(self):
        self.bridge.send_zone("terminal")
        self.assertEqual(self.bridge._cached_zone, "terminal")

        self.bridge.send_rules(["python", "git"])
        self.assertEqual(self.bridge._cached_rules, "python, git")

        self.bridge.send_command("git status", status="recognized")
        self.assertEqual(self.bridge._cached_command, "git status")
        self.assertEqual(self.bridge._cached_status, "recognized")

        # Verify duplicate method set_zone is not present
        self.assertFalse(hasattr(self.bridge, "set_zone"))

    def test_replay_state_snapshot(self):
        self.bridge.send_update(
            command="format file",
            rules="Python",
            adce_zone="editor",
            status="recognized",
            mic_state="listening",
        )

        replays = self.bridge._get_replay_payloads()
        self.assertEqual(len(replays), 1)
        snapshot = replays[0]
        self.assertEqual(snapshot["command"], "format file")
        self.assertEqual(snapshot["rules"], "Python")
        self.assertEqual(snapshot["adce_zone"], "editor")
        self.assertEqual(snapshot["status"], "recognized")
        self.assertEqual(snapshot["mic_state"], "listening")
        self.assertIn("timestamp_ms", snapshot)


class TestCleanedPrinterHandlers(unittest.TestCase):
    """Verifies printer handlers ignore system messages and handle commands and rejections cleanly."""

    def test_dynamic_cursor_printer_handler_ignores_system_messages(self):
        mock_bridge = MagicMock()
        handler = DynamicCursorPrintHandler(bridge=mock_bridge)

        handler.handle_message([
            "@ Caster: Microphone is sleeping",
            "@ Microphone is on",
            "@ Microphone is off",
            "@ ready",
        ])
        mock_bridge.update_mic_layer.assert_not_called()

    def test_taskbar_hud_printer_handler_ignores_system_messages(self):
        mock_bridge = MagicMock()
        handler = TaskbarHudPrintHandler(bridge=mock_bridge)

        # System messages must be ignored completely
        handler.handle_message([
            "@ Caster: Microphone is sleeping",
            "@ Microphone is off",
            "@ System ready",
        ])
        mock_bridge.send_update.assert_not_called()

    def test_taskbar_hud_printer_handler_handles_commands_and_rejections(self):
        mock_bridge = MagicMock()
        handler = TaskbarHudPrintHandler(bridge=mock_bridge)

        # 1. Recognized command ($)
        with patch("castervoice.lib.control.nexus") as mock_nexus:
            mock_nexus.return_value.engine_modes_manager.get_mic_mode.return_value = "on"
            handler.handle_message(["$ open explorer"])

        mock_bridge.send_update.assert_called_with(command="open explorer", status="recognized")

        # 2. Rejected utterance (#)
        mock_bridge.reset_mock()
        handler.handle_message(["# rejected recognition"])
        mock_bridge.send_update.assert_called_with(command="[?]", status="error")

    def test_taskbar_hud_printer_handler_filters_mic_phrases(self):
        mock_bridge = MagicMock()
        handler = TaskbarHudPrintHandler(bridge=mock_bridge)

        with patch("castervoice.lib.control.nexus") as mock_nexus:
            mock_nexus.return_value.engine_modes_manager.get_mic_mode.return_value = "on"
            handler.handle_message(["$ caster sleep", "$ sleep", "$ wake up"])

        # Mic control command phrases must not trigger recognized command update
        mock_bridge.send_update.assert_not_called()


if __name__ == "__main__":
    unittest.main()
