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
import subprocess
import logging
from dragonfly import get_current_engine
from castervoice.lib import printer
try:
    from castervoice.lib.plugin import PluginBase
except ImportError:
    try:
        from plugins.common.plugin_base import PluginBase
    except ImportError:
        from ..common.plugin_base import PluginBase
from castervoice.asynch import hud_support

_logger = logging.getLogger("caster.plugins.themed_hud")

_DIR = os.path.dirname(os.path.abspath(__file__))
if _DIR not in sys.path:
    sys.path.insert(0, _DIR)

_HUD_RUNNER_PATH = os.path.join(_DIR, "hud_runner.py")
_HUD_JOB_OBJECT = None


def _get_or_create_hud_job():
    global _HUD_JOB_OBJECT
    if sys.platform != "win32":
        return None
    if _HUD_JOB_OBJECT is not None:
        return _HUD_JOB_OBJECT
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        job = kernel32.CreateJobObjectW(None, None)
        if not job:
            return None

        class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
                ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class IO_COUNTERS(ctypes.Structure):
            _fields_ = [(f, ctypes.c_uint64) for f in [
                "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                "ReadTransferCount", "WriteTransferCount", "OtherTransferCount"
            ]]

        class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                ("IoInfo", IO_COUNTERS),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryLimit", ctypes.c_size_t),
                ("PeakJobMemoryLimit", ctypes.c_size_t),
            ]

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        JobObjectExtendedLimitInformation = 9
        res = kernel32.SetInformationJobObject(
            job, JobObjectExtendedLimitInformation,
            ctypes.byref(info), ctypes.sizeof(info)
        )
        if not res:
            kernel32.CloseHandle(job)
            return None
        _HUD_JOB_OBJECT = job
        return _HUD_JOB_OBJECT
    except Exception:
        return None


def _bind_process_to_job(proc):
    if sys.platform != "win32" or proc is None:
        return
    try:
        job = _get_or_create_hud_job()
        if job and hasattr(proc, "_handle") and proc._handle:
            import ctypes
            ctypes.windll.kernel32.AssignProcessToJobObject(job, int(proc._handle))
    except Exception:
        pass


class ThemedHudPlugin(PluginBase):
    name = "themed_hud"
    version = "2.0.0"
    description = "Modular, Customizable PyQt Heads-Up Display with QSS Themes and ADCE Context Strip"
    replaces_hud = True

    def __init__(self):
        super(ThemedHudPlugin, self).__init__()
        self._print_handler = None
        self._adce_client = None
        self._process = None

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
                if self._process is not None and self._process.poll() is None:
                    _logger.info("Themed HUD runner process is already running.")
                    return

                # Stop legacy HUD instance if active so port 8338 is released cleanly
                try:
                    hud_support.stop_hud()
                except Exception:
                    pass

                python_bin = sys.executable
                try:
                    from castervoice.lib import settings
                    if settings.SETTINGS and "paths" in settings.SETTINGS and "PYTHONW" in settings.SETTINGS["paths"]:
                        cand = settings.SETTINGS["paths"]["PYTHONW"]
                        if os.path.isfile(cand):
                            python_bin = cand
                except Exception:
                    pass

                self._process = subprocess.Popen([python_bin, _HUD_RUNNER_PATH])
                _bind_process_to_job(self._process)
                _logger.info("Themed HUD runner started: %s (PID: %s)", _HUD_RUNNER_PATH, self._process.pid)

                # Route Caster core HUD paths so voice commands ("start caster hud", "restart caster hud")
                # always interact with Themed HUD instead of falling back to legacy asynch/hud.py.
                try:
                    from castervoice.lib import settings
                    if settings.SETTINGS and "paths" in settings.SETTINGS:
                        self._original_hud_path = settings.SETTINGS["paths"].get("HUD_PATH")
                        settings.SETTINGS["paths"]["HUD_PATH"] = _HUD_RUNNER_PATH
                    hud_support._CURRENT_HUD_PATH = _HUD_RUNNER_PATH
                    hud_support._HUD_PROCESS = self._process
                except Exception as ex:
                    _logger.debug("Failed to route core hud_support paths to Themed HUD: %s", ex)
            except Exception as ex:
                printer.out("Themed HUD: Failed to start HUD process: {}".format(ex))
                _logger.exception("Themed HUD startup error:")

    def stop(self):
        super(ThemedHudPlugin, self).stop()
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
            self._nexus.engine_modes_manager.remove_mic_listener(self._on_mic_mode_changed)
        if self._adce_client:
            try:
                self._adce_client.remove_context_listener(self._on_adce_context_changed)
            except Exception:
                pass
            self._adce_client = None

        try:
            from hud.ipc.client import get_telemetry_publisher

            pub = get_telemetry_publisher()
            if pub:
                pub.stop()
        except Exception:
            pass

        # Restore original HUD path in core settings if modified
        try:
            from castervoice.lib import settings
            if hasattr(self, "_original_hud_path") and self._original_hud_path and settings.SETTINGS and "paths" in settings.SETTINGS:
                settings.SETTINGS["paths"]["HUD_PATH"] = self._original_hud_path
            if hasattr(self, "_original_hud_path") and self._original_hud_path:
                hud_support._CURRENT_HUD_PATH = self._original_hud_path
            if getattr(hud_support, "_HUD_PROCESS", None) is self._process:
                hud_support._HUD_PROCESS = None
        except Exception as ex:
            _logger.debug("Failed to restore core hud_support paths: %s", ex)

        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=1.5)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None

    def get_rules(self):
        try:
            from rules import get_rule

            return [get_rule()]
        except Exception as ex:
            _logger.warning("Failed to load Themed HUD companion rules: %s", ex)
            return []


def get_plugin():
    return ThemedHudPlugin()
