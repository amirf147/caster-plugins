"""
HUD IPC Server Thread (HUD Process Side).
Listens for incoming ndjson telemetry streams and bridges events across the thread boundary into Qt.
"""

import socket
import threading
import time
import logging
from typing import Callable, Optional

from hud.core.constants import DEFAULT_HUD_HOST, DEFAULT_HUD_PORT
from hud.core.events import event_from_dict, HudEvent
from hud.ipc.protocol import NdjsonStreamDecoder

_logger = logging.getLogger("caster.hud.ipc.server")


class IpcServerThread:
    """
    Background socket listener thread running inside the HUD process.
    Accepts telemetry connections from Caster and dispatches parsed HudEvents to the Qt GUI thread.
    """

    def __init__(self, host: str = DEFAULT_HUD_HOST, port: int = DEFAULT_HUD_PORT,
                 on_event: Optional[Callable[[HudEvent], None]] = None):
        self._host = host
        self._port = port
        self._on_event = on_event
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._server_sock: Optional[socket.socket] = None
        self._lock = threading.Lock()

    def start(self):
        """Binds socket and starts server loop thread."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run_server, name="HUD-IPC-Server", daemon=True)
            self._thread.start()

    def stop(self):
        """Stops listener thread and closes server socket."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except Exception:
                pass

    def _run_server(self):
        """Main socket listening loop."""
        try:
            self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind((self._host, self._port))
            self._server_sock.listen(5)
            self._server_sock.settimeout(1.0)
            _logger.info("HUD IPC server listening on %s:%s", self._host, self._port)
        except Exception as ex:
            _logger.error("Failed to bind HUD IPC server on %s:%s: %s", self._host, self._port, ex)
            return

        decoder = NdjsonStreamDecoder()

        while self._running:
            client_sock = None
            try:
                client_sock, client_addr = self._server_sock.accept()
                client_sock.settimeout(1.0)
                _logger.debug("Client connected to HUD IPC from %s", client_addr)

                while self._running:
                    try:
                        chunk = client_sock.recv(4096)
                        if not chunk:
                            break  # Client disconnected

                        for event_dict in decoder.feed(chunk):
                            event = event_from_dict(event_dict)
                            if self._on_event:
                                self._on_event(event)

                    except socket.timeout:
                        continue
                    except (socket.error, OSError):
                        break

            except socket.timeout:
                continue
            except Exception as ex:
                if self._running:
                    _logger.debug("HUD IPC accept error: %s", ex)
            finally:
                if client_sock:
                    try:
                        client_sock.close()
                    except Exception:
                        pass
                decoder.clear()
