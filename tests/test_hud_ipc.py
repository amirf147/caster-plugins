"""
Unit tests for Caster HUD IPC (ndjson framing, drop-oldest queue, and Client-Server loop).
"""

import time
import unittest
from hud.core.events import MicStateEvent, RecognitionEvent
from hud.ipc.protocol import encode_event, NdjsonStreamDecoder
from hud.ipc.client import AsyncTelemetryPublisher
from hud.ipc.server import IpcServerThread


class TestHudIpc(unittest.TestCase):

    def test_ndjson_encoding(self):
        ev = MicStateEvent(mode="sleeping")
        encoded = encode_event(ev)
        self.assertTrue(encoded.endswith(b"\n"))
        self.assertIn(b'"event_type":"mic_state"', encoded)
        self.assertIn(b'"mode":"sleeping"', encoded)

    def test_ndjson_decoder_partial_chunks(self):
        decoder = NdjsonStreamDecoder()
        ev1 = MicStateEvent(mode="sleeping")
        ev2 = RecognitionEvent(phrase="hello world")
        
        full_stream = encode_event(ev1) + encode_event(ev2)
        
        # Split into arbitrary 7-byte chunks to simulate TCP fragmentation
        chunk_size = 7
        received_events = []
        for i in range(0, len(full_stream), chunk_size):
            chunk = full_stream[i:i + chunk_size]
            for parsed in decoder.feed(chunk):
                received_events.append(parsed)

        self.assertEqual(len(received_events), 2)
        self.assertEqual(received_events[0]["event_type"], "mic_state")
        self.assertEqual(received_events[0]["mode"], "sleeping")
        self.assertEqual(received_events[1]["event_type"], "recognition")
        self.assertEqual(received_events[1]["phrase"], "hello world")

    def test_queue_saturation_drop_oldest_policy(self):
        """
        Verify that publishing into a full queue evicts the oldest item
        and never raises queue.Full or blocks the caller.
        """
        pub = AsyncTelemetryPublisher(max_queue_size=3)
        # Do not start worker thread so queue fills up
        pub.publish(RecognitionEvent(phrase="msg 1"))
        pub.publish(RecognitionEvent(phrase="msg 2"))
        pub.publish(RecognitionEvent(phrase="msg 3"))
        
        self.assertEqual(pub._queue.qsize(), 3)
        
        # Publish 4th item: should evict msg 1
        pub.publish(RecognitionEvent(phrase="msg 4"))
        self.assertEqual(pub._queue.qsize(), 3)
        
        item1 = pub._queue.get_nowait()
        item2 = pub._queue.get_nowait()
        item3 = pub._queue.get_nowait()
        
        self.assertEqual(item1.phrase, "msg 2")
        self.assertEqual(item2.phrase, "msg 3")
        self.assertEqual(item3.phrase, "msg 4")

    def test_client_server_socket_loop(self):
        test_port = 19338
        received_events = []

        def handle_event(ev):
            received_events.append(ev)

        server = IpcServerThread(port=test_port, on_event=handle_event)
        server.start()

        client = AsyncTelemetryPublisher(port=test_port)
        client.start()

        try:
            # Allow connection handshake
            time.sleep(0.3)
            
            client.publish(MicStateEvent(mode="sleeping"))
            client.publish(RecognitionEvent(phrase="test phrase", rule_name="TestRule"))
            
            # Wait for background dispatch
            time.sleep(0.3)
            
            self.assertEqual(len(received_events), 2)
            self.assertIsInstance(received_events[0], MicStateEvent)
            self.assertEqual(received_events[0].mode, "sleeping")
            self.assertIsInstance(received_events[1], RecognitionEvent)
            self.assertEqual(received_events[1].phrase, "test phrase")
        finally:
            client.stop()
            server.stop()


if __name__ == "__main__":
    unittest.main()
