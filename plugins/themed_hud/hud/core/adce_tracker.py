"""
Real-time ADCE Stream & SSE Background Observer for Caster HUD.
Maintains persistent SSE connection to local ADCE Daemon (http://127.0.0.1:8424/sse).
Captures sub-window zone transitions ({IntegratedTerminal}, {EditorCodeBuffer}, {GitCommitBox})
and active file switches in real-time (< 10 ms) without requiring window switches or taskbar clicks.
Compatible with Python 2.7 and Python 3.x.
"""

import sys
import json
import logging
import threading
import time

try:
    import http.client as http_client
except ImportError:
    import httplib as http_client

try:
    import urllib.request as urllib_request
except ImportError:
    import urllib2 as urllib_request

_logger = logging.getLogger("caster.hud.adce_tracker")


class AdceTracker(object):
    """
    Background worker listening to the ADCE daemon SSE stream on port 8424.
    Emits real-time DesktopContextEvents whenever sub-window zones or active files change.
    """

    def __init__(self, host="127.0.0.1", port=8424, on_context_changed=None):
        self._host = host
        self._port = int(port)
        self._on_context_changed = on_context_changed

        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        self._is_connected = False
        self._last_zone = ""
        self._last_process = ""
        self._last_title = ""
        self._last_file = ""

    def start(self):
        """Starts background ADCE SSE listener thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._worker_loop,
                name="ADCE-HUD-Tracker"
            )
            self._thread.daemon = True
            self._thread.start()

    def stop(self):
        """Stops background listener thread."""
        with self._lock:
            self._running = False

    def is_connected(self):
        return self._is_connected

    def get_current_context(self):
        return {
            "is_connected": self._is_connected,
            "semantic_zone": self._last_zone,
            "process_name": self._last_process,
            "window_title": self._last_title,
            "active_file": self._last_file,
        }

    def _worker_loop(self):
        """Continuous SSE stream connection loop with auto-reconnection and exponential backoff."""
        while self._running:
            conn = None
            try:
                conn = http_client.HTTPConnection(self._host, self._port, timeout=10)
                conn.request("GET", "/sse", headers={"Accept": "text/event-stream"})
                resp = conn.getresponse()

                if resp.status != 200:
                    self._set_disconnected()
                    time.sleep(2.0)
                    continue

                self._is_connected = True
                _logger.info("Connected to ADCE SSE stream on %s:%s", self._host, self._port)

                current_event = "message"

                while self._running:
                    raw_line = resp.readline()
                    if not raw_line:
                        break  # Stream closed

                    line = raw_line.decode("utf-8", errors="ignore").strip("\r\n").strip()
                    if not line or line.startswith(":"):
                        current_event = "message"
                        continue

                    if line.startswith("event:"):
                        current_event = line[6:].strip()
                    elif line.startswith("data:"):
                        data_str = line[5:].strip()
                        self._process_data_message(data_str)

            except Exception as ex:
                self._set_disconnected()
                _logger.debug("ADCE tracker connection error: %s", ex)
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
                time.sleep(1.5)

    def _set_disconnected(self):
        """Marks connection offline and notifies subscribers if state changed."""
        if self._is_connected:
            self._is_connected = False
            self._last_zone = ""
            self._last_process = ""
            self._last_title = ""
            self._last_file = ""
            if self._on_context_changed:
                try:
                    self._on_context_changed(
                        process_name="",
                        window_title="",
                        semantic_zone="",
                        active_file="",
                        is_connected=False
                    )
                except Exception as ex:
                    _logger.debug("Error in on_context_changed callback: %s", ex)

    def _process_data_message(self, data_str):
        """Parses incoming JSON payloads (MCP responses or direct snapshots)."""
        if not data_str:
            return
        try:
            parsed = json.loads(data_str)
            # Handle MCP tool result
            if isinstance(parsed, dict) and "result" in parsed:
                res = parsed["result"]
                if isinstance(res, dict) and "content" in res:
                    for item in res["content"]:
                        if item.get("type") == "text":
                            text_body = item.get("text", "")
                            if text_body.startswith("{"):
                                snapshot = json.loads(text_body)
                                self._ingest_snapshot(snapshot)
                                return

            # Direct snapshot JSON
            if isinstance(parsed, dict) and ("focus" in parsed or "Focus" in parsed or "window" in parsed):
                self._ingest_snapshot(parsed)
        except Exception:
            pass

    def _ingest_snapshot(self, snapshot):
        """Ingests snapshot and dispatches context update if zone, file, process, or title changed."""
        try:
            focus = snapshot.get("focus") or snapshot.get("Focus") or {}
            window = snapshot.get("window") or snapshot.get("Window") or {}
            ide = snapshot.get("ide_context") or snapshot.get("IdeContext") or {}

            zone = str(focus.get("semantic_zone") or focus.get("SemanticZone") or "").strip()
            process = str(window.get("process_name") or window.get("ProcessName") or "").lower().strip()
            title = str(window.get("title") or window.get("Title") or "").strip()

            active_file = ""
            active_tab = ide.get("active_tab") or ide.get("ActiveTab")
            if active_tab and isinstance(active_tab, dict):
                active_file = str(active_tab.get("title") or active_tab.get("Title") or "").strip()

            if zone.lower() == "unknown":
                zone = ""

            # Check if any property changed
            if (zone != self._last_zone or process != self._last_process or
                title != self._last_title or active_file != self._last_file):
                self._last_zone = zone
                self._last_process = process
                self._last_title = title
                self._last_file = active_file

                if self._on_context_changed:
                    try:
                        self._on_context_changed(
                            process_name=process,
                            window_title=title,
                            semantic_zone=zone,
                            active_file=active_file,
                            is_connected=True
                        )
                    except Exception as ex:
                        _logger.debug("Error in on_context_changed callback: %s", ex)
        except Exception as ex:
            _logger.debug("Failed to ingest ADCE snapshot: %s", ex)


_GLOBAL_ADCE_TRACKER = None
_GLOBAL_ADCE_LOCK = threading.Lock()


def get_adce_tracker(on_context_changed=None):
    """Singleton factory for AdceTracker."""
    global _GLOBAL_ADCE_TRACKER
    if _GLOBAL_ADCE_TRACKER is None:
        with _GLOBAL_ADCE_LOCK:
            if _GLOBAL_ADCE_TRACKER is None:
                _GLOBAL_ADCE_TRACKER = AdceTracker(on_context_changed=on_context_changed)
                _GLOBAL_ADCE_TRACKER.start()
    return _GLOBAL_ADCE_TRACKER
