# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Taskbar HUD Plugin

Integrates Caster voice recognition and mic telemetry with the Windows 11
Taskbar HUD Windhawk mod via Named Pipe with unified desktop context.
"""

import logging
import sys

from castervoice.lib import printer
try:
    from castervoice.lib.plugin import PluginBase
except ImportError:
    try:
        from plugins.common.plugin_base import PluginBase
    except ImportError:
        from ..common.plugin_base import PluginBase

try:
    from plugins.common.desktop_context import DesktopContextProvider
except ImportError:
    try:
        from ..common.desktop_context import DesktopContextProvider
    except ImportError:
        DesktopContextProvider = None

from .bridge import TaskbarHudBridgeClient
from .printer_handler import TaskbarHudPrintHandler
try:
    from plugins.common.context_resolver import resolve_active_rules
except ImportError:
    try:
        from ..common.context_resolver import resolve_active_rules
    except ImportError:
        try:
            from caster_user_content.plugins.common.context_resolver import resolve_active_rules
        except ImportError:
            def resolve_active_rules(**kwargs):
                return []

_logger = logging.getLogger("caster.plugins.taskbar_hud")


class TaskbarHudPlugin(PluginBase):
    name = "taskbar_hud"
    version = "1.1.0"
    description = "Windows 11 Taskbar HUD Windhawk Mod Bridge with Decoupled Context Engine"

    def __init__(self):
        super(TaskbarHudPlugin, self).__init__()
        self._bridge = None
        self._print_handler = None
        self._adce_connected = False
        self._running = False

    def initialize(self, nexus, config):
        super(TaskbarHudPlugin, self).initialize(nexus, config)
        if sys.platform != "win32":
            _logger.warning("taskbar_hud plugin is only supported on Windows (win32). Skipping initialization.")
            return

        pipe_name = config.get("pipe_name", "CasterTaskbarHud")
        self._bridge = TaskbarHudBridgeClient.get_instance(pipe_name=pipe_name)

        # 1. Register delegating printer message handler
        self._print_handler = TaskbarHudPrintHandler(bridge=self._bridge)
        printer.get_delegating_handler().register_handler(self._print_handler)

        # 2. Register mic state observer on EngineModesManager
        if nexus and hasattr(nexus, "engine_modes_manager") and nexus.engine_modes_manager:
            nexus.engine_modes_manager.add_mic_listener(self._on_mic_mode_changed)

        # 3. Optionally attach to ADCE context listener if ADCE plugin is loaded
        try:
            from adce import add_context_listener

            add_context_listener(self._on_adce_context_changed)
        except Exception:
            try:
                from caster_user_content.plugins.adce import add_context_listener

                add_context_listener(self._on_adce_context_changed)
            except Exception:
                pass

    def _on_mic_mode_changed(self, mode):
        """Dispatches mic state transitions to Taskbar HUD."""
        if not self._bridge:
            return
        status = "sleeping" if mode in ("sleeping", "off") else "idle"
        command = "Sleeping" if mode in ("sleeping", "off") else "Ready"
        self._bridge.send_update(
            mic_state=mode,
            status=status,
            command=command,
        )

    def _on_adce_context_changed(
        self, process_name="", window_title="", semantic_zone="", active_file="", is_connected=True, **kwargs
    ):
        """Forwards ADCE sub-window zone transitions and active rules to Taskbar HUD."""
        self._adce_connected = bool(is_connected)
        if not self._bridge:
            return
        zone = semantic_zone if (is_connected and semantic_zone) else "--"
        rules_str = "Global"
        if is_connected and process_name:
            try:
                active = resolve_active_rules(
                    process_name=process_name,
                    window_title=window_title,
                    semantic_zone=semantic_zone,
                )
                rules_str = ", ".join(active) if active else "Global"
            except Exception as ex:
                _logger.debug("Context resolution error: %s", ex)
        if self._bridge._cached_rules != rules_str or self._bridge._cached_zone != zone:
            _logger.debug("[Taskbar HUD] Focus: '%s' -> Rules: '%s' | Zone: '%s'", process_name, rules_str, zone)
        self._bridge.send_update(adce_zone=zone, rules=rules_str)

    def _on_desktop_context_changed(self, snapshot):
        """Forwards desktop context snapshots and active rules to Taskbar HUD."""
        if not self._bridge or not self._running:
            return

        zone = snapshot.semantic_zone if (snapshot.is_adce_connected and snapshot.semantic_zone) else "--"
        rules_str = "Global"

        if snapshot.process_name or snapshot.window_title:
            try:
                active = resolve_active_rules(
                    process_name=snapshot.process_name,
                    window_title=snapshot.window_title,
                    semantic_zone=snapshot.semantic_zone if snapshot.is_adce_connected else "",
                    hwnd=snapshot.hwnd,
                )
                rules_str = ", ".join(active) if active else "Global"
            except Exception as ex:
                _logger.debug("Context resolution error: %s", ex)

        if self._bridge._cached_rules != rules_str or self._bridge._cached_zone != zone:
            _logger.debug(
                "[Taskbar HUD] Focus: '%s' -> Rules: '%s' | Zone: '%s'",
                snapshot.process_name,
                rules_str,
                zone,
            )

        self._bridge.send_update(adce_zone=zone, rules=rules_str)

    def start(self):
        super(TaskbarHudPlugin, self).start()
        if sys.platform != "win32":
            return
        self._running = True

        if self._bridge:
            self._bridge.start()

            # Push initial baseline state immediately on startup
            current_mic = "on"
            if self._nexus and hasattr(self._nexus, "engine_modes_manager") and self._nexus.engine_modes_manager:
                current_mic = self._nexus.engine_modes_manager.get_mic_mode() or "on"

            status = "sleeping" if current_mic in ("sleeping", "off") else "idle"
            command = "Sleeping" if current_mic in ("sleeping", "off") else "Ready"

            self._bridge.send_update(
                mic_state=current_mic,
                status=status,
                command=command,
                rules="Global",
                adce_zone="--",
            )

        if DesktopContextProvider:
            DesktopContextProvider.get_instance().add_listener(self._on_desktop_context_changed)

    def stop(self):
        super(TaskbarHudPlugin, self).stop()
        self._running = False

        if DesktopContextProvider:
            DesktopContextProvider.get_instance().remove_listener(self._on_desktop_context_changed)

        try:
            from adce import remove_context_listener
            remove_context_listener(self._on_adce_context_changed)
        except Exception:
            try:
                from caster_user_content.plugins.adce import remove_context_listener
                remove_context_listener(self._on_adce_context_changed)
            except Exception:
                pass

        if self._bridge:
            self._bridge.stop()
        if self._print_handler:
            dh = printer.get_delegating_handler()
            if hasattr(dh, "unregister_handler"):
                dh.unregister_handler(self._print_handler)
            elif hasattr(dh, "_handlers"):
                try:
                    if self._print_handler in dh._handlers:
                        dh._handlers.remove(self._print_handler)
                except Exception:
                    pass
            self._print_handler = None
        if self._nexus and hasattr(self._nexus, "engine_modes_manager") and self._nexus.engine_modes_manager:
            try:
                self._nexus.engine_modes_manager.remove_mic_listener(self._on_mic_mode_changed)
            except Exception:
                pass


def get_plugin():
    return TaskbarHudPlugin()
