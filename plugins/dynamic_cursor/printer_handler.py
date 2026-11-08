# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Printer status message handler for Dynamic Cursor.

Intercepts formatted engine messages from castervoice.lib.printer and updates
the Dynamic Cursor bridge client as a redundant trigger alongside engine modes.
"""

import logging

try:
    from castervoice.lib import printer
    BaseMessageHandler = printer.BaseMessageHandler
except ImportError:
    class BaseMessageHandler(object):
        pass

_logger = logging.getLogger("caster.plugins.dynamic_cursor.printer_handler")


class DynamicCursorPrintHandler(BaseMessageHandler):
    """
    Message handler dispatching microphone mode transitions to Dynamic Cursor.
    """

    def __init__(self, bridge=None):
        super(DynamicCursorPrintHandler, self).__init__()
        self._bridge = bridge

    def set_bridge(self, bridge):
        """Assigns the active bridge client instance."""
        self._bridge = bridge

    def handle_message(self, items):
        """Processes printer stream items for microphone status transitions."""
        if not self._bridge:
            try:
                from .bridge import get_dynamic_cursor_bridge
                self._bridge = get_dynamic_cursor_bridge()
            except ImportError:
                return

        if not self._bridge:
            return

        for item in items:
            raw = str(item).strip()
            if not raw:
                continue

            # Process system/status messages prefixed with '@'
            if raw.startswith("@"):
                sys_msg = raw[1:].strip().lower()
                if "sleeping" in sys_msg:
                    self._bridge.update_mic_layer("sleeping")
                elif "ready" in sys_msg or "microphone is on" in sys_msg:
                    self._bridge.update_mic_layer("on")
                elif "microphone is off" in sys_msg or "muted" in sys_msg:
                    self._bridge.update_mic_layer("off")
