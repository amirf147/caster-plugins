# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Process dispatch bridge for launching and managing the Plugin Manager GUI subprocess.
Provides non-blocking execution from Caster engine and Dragonfly rule threads.
"""

import ctypes
import logging
import os
from pathlib import Path
import subprocess
import sys
from typing import Optional

_logger = logging.getLogger("caster.plugins.plugin_manager.runner_bridge")

_active_process: Optional[subprocess.Popen] = None


def get_active_process() -> Optional[subprocess.Popen]:
    """Returns the currently active subprocess handle if alive, else None."""
    global _active_process
    if _active_process is not None:
        if _active_process.poll() is None:
            return _active_process
        _active_process = None
    return None


def bring_window_to_front(window_title: str = "Caster Plugin Manager") -> bool:
    """Attempts to find and focus an existing window by title using Win32 API."""
    if sys.platform != "win32":
        return False

    try:
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, window_title)
        if hwnd:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            return True
    except Exception as ex:
        _logger.debug("Failed to focus window '%s': %s", window_title, ex)
    return False


def _get_log_file() -> Optional[Path]:
    """Resolves log filepath for child process diagnostic output."""
    try:
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if local_app_data:
            log_dir = Path(local_app_data) / "caster" / "data"
            log_dir.mkdir(parents=True, exist_ok=True)
            return log_dir / "plugin_manager_gui.log"
    except Exception:
        pass
    return None


def open_manager_process() -> subprocess.Popen:
    """
    Launches the Plugin Manager GUI in an isolated child process without blocking
    the calling speech recognition thread. Reuses or focuses existing process if active.
    """
    global _active_process

    active = get_active_process()
    if active is not None:
        _logger.info("Plugin Manager process already running (PID: %d). Bringing to front.", active.pid)
        bring_window_to_front()
        return active

    python_bin = sys.executable

    # Dynamically resolve root directory containing the 'plugins' package
    package_root = str(Path(__file__).resolve().parents[2])

    cmd = [python_bin, "-m", "plugins.plugin_manager.gui.runner"]

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{package_root}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else package_root

    _logger.info("Launching Plugin Manager GUI subprocess: %s", cmd)

    log_path = _get_log_file()
    out_fh = None
    if log_path:
        try:
            out_fh = open(log_path, "a", encoding="utf-8")
        except Exception:
            out_fh = None

    proc = subprocess.Popen(
        cmd,
        env=env,
        stdout=out_fh or subprocess.DEVNULL,
        stderr=subprocess.STDOUT if out_fh else subprocess.DEVNULL,
    )
    _active_process = proc
    return proc


def close_manager() -> bool:
    """Terminates the active Plugin Manager subprocess if currently running."""
    global _active_process
    active = get_active_process()
    if active is not None:
        try:
            active.terminate()
            active.wait(timeout=1.0)
            _active_process = None
            _logger.info("Plugin Manager process terminated.")
            return True
        except Exception as ex:
            _logger.warning("Failed to terminate Plugin Manager process: %s", ex)
            try:
                active.kill()
                _active_process = None
                return True
            except Exception:
                return False
    return False


def refresh_manager() -> bool:
    """Signals or focuses the active manager window to trigger a refresh."""
    active = get_active_process()
    if active is not None:
        bring_window_to_front()
        return True
    return False
