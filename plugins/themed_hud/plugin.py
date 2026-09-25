# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Next-Gen Modular/Themed HUD Plugin

Wraps the advanced, customizable Caster Heads-Up Display featuring QSS themes,
status bar, active rules tag bar, ADCE sub-window strip, opacity controls,
frameless drag mode, and IPC telemetry.
"""

import os
import sys
import logging
from dragonfly import get_current_engine
from castervoice.lib import printer
from castervoice.lib.plugin import PluginBase
from castervoice.asynch import hud_support

_logger = logging.getLogger("caster.plugins.themed_hud")

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

_HUD_RUNNER_PATH = os.path.join(_DIR, "hud_runner.py")


class ThemedHudPlugin(PluginBase):
    name = "themed_hud"
    version = "2.0.0"
    description = "Modular, Customizable PyQt Heads-Up Display with QSS Themes and ADCE Context Strip"
    replaces_hud = True

    def __init__(self):
        super(ThemedHudPlugin, self).__init__()
        self._print_handler = None
        self._adce_client = None

    def initialize(self, nexus, config):
        super(ThemedHudPlugin, self).initialize(nexus, config)
        dh = printer.get_delegating_handler()
        if not dh.has_handler(hud_support.HudPrintMessageHandler):
            self._print_handler = hud_support.HudPrintMessageHandler()
            dh.register_handler(self._print_handler)
            _logger.info("Themed HUD print message handler registered.")

        # 2. Register mic state observer on EngineModesManager
        if nexus and hasattr(nexus, "engine_modes_manager") and nexus.engine_modes_manager:
            nexus.engine_modes_manager.add_mic_listener(self._on_mic_mode_changed)

        # 3. Optionally attach to ADCE context listener if ADCE plugin is loaded
        try:
            from plugins.adce.client import get_adce_client

            client = get_adce_client()
            if client:
                self._adce_client = client
                client.add_context_listener(self._on_adce_context_changed)
                ctx = client.get_current_context()
                if ctx and ctx.get("is_connected"):
                    self._on_adce_context_changed(**ctx)
        except Exception as ex:
            _logger.debug("ADCE plugin listener registration failed: %s", ex)

    def _on_mic_mode_changed(self, mode):
        """Forwards microphone mode changes to Themed HUD via IPC."""
        try:
            from hud.ipc.client import get_telemetry_publisher
            from hud.core.events import MicStateEvent

            pub = get_telemetry_publisher()
            if pub:
                pub.publish(MicStateEvent(mode=str(mode)))
        except Exception as ex:
            _logger.debug("Themed HUD mic state dispatch error: %s", ex)

    def _on_adce_context_changed(
        self, process_name="", window_title="", semantic_zone="", active_file="", is_connected=True
    ):
        """Dispatches real-time ADCE desktop context and resolved active voice rules to Themed HUD."""
        try:
            from hud.ipc.client import get_telemetry_publisher
            from hud.core.events import DesktopContextEvent, ActiveRulesEvent
            from .context_resolver import resolve_active_rules

            pub = get_telemetry_publisher()
            if not pub:
                return

            # 1. Update ADCE dynamic context strip
            pub.publish(
                DesktopContextEvent(
                    process_name=process_name,
                    window_title=window_title,
                    semantic_zone=semantic_zone,
                    active_file=active_file,
                    is_connected=is_connected,
                )
            )

            # 2. Resolve active rules and update Active Rules strip
            active = []
            if is_connected and process_name:
                active = resolve_active_rules(
                    process_name=process_name,
                    window_title=window_title,
                    semantic_zone=semantic_zone,
                )
            pub.publish(ActiveRulesEvent(rules=active))
        except Exception as ex:
            _logger.debug("Themed HUD ADCE context dispatch error: %s", ex)

    def start(self):
        super(ThemedHudPlugin, self).start()
        engine = get_current_engine()
        engine_name = engine.name if engine else ""
        if engine_name != "text":
            try:
                hud_support.start_hud(hud_path=_HUD_RUNNER_PATH)
                _logger.info("Themed HUD runner started: %s", _HUD_RUNNER_PATH)
            except Exception as ex:
                printer.out("Themed HUD: Failed to start HUD process: {}".format(ex))
                _logger.exception("Themed HUD startup error:")

    def stop(self):
        super(ThemedHudPlugin, self).stop()
        if self._print_handler:
            printer.get_delegating_handler().unregister_handler(self._print_handler)
            self._print_handler = None
        if self._nexus and hasattr(self._nexus, "engine_modes_manager") and self._nexus.engine_modes_manager:
            self._nexus.engine_modes_manager.remove_mic_listener(self._on_mic_mode_changed)
        if self._adce_client:
            try:
                self._adce_client.remove_context_listener(self._on_adce_context_changed)
            except Exception:
                pass
            self._adce_client = None
        hud_support.stop_hud()
        try:
            from hud.ipc.client import get_telemetry_publisher

            pub = get_telemetry_publisher()
            if pub:
                pub.stop()
        except Exception:
            pass

    def get_rules(self):
        try:
            from rules import get_rule

            return [get_rule()]
        except Exception as ex:
            _logger.warning("Failed to load Themed HUD companion rules: %s", ex)
            return []


def get_plugin():
    return ThemedHudPlugin()

