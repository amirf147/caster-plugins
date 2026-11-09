# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Printer status message handler for Dynamic Cursor.

Maintains printer message interceptor interface for Caster's printer pipeline.
Microphone transitions are handled directly via EngineModesManager in plugin.py.
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
    Message handler for Dynamic Cursor printer messages.
    """

    def __init__(self, bridge=None):
        super(DynamicCursorPrintHandler, self).__init__()
        self._bridge = bridge

    def set_bridge(self, bridge):
        """Assigns the active bridge client instance."""
        self._bridge = bridge

    def handle_message(self, items):
        """
        Processes printer stream items.

        System status messages (@) are ignored; microphone mode transitions
        are handled strictly via EngineModesManager.add_mic_listener in plugin.py.
        """
        pass
