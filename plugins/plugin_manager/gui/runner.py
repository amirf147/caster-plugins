# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Standalone launcher and lifecycle coordinator for Caster Plugin Manager GUI.
"""

import sys
from typing import Optional

try:
    from PySide2 import QtWidgets
except ImportError:
    try:
        from PyQt5 import QtWidgets
    except ImportError:
        from castervoice.lib.qt import QtWidgets

from ..core.registry import PluginRegistry
from .window import PluginManagerWindow


def get_or_create_app() -> QtWidgets.QApplication:
    """Returns the existing QApplication instance or creates a new one."""
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
    return app


def show_plugin_manager(registry: Optional[PluginRegistry] = None) -> PluginManagerWindow:
    """
    Creates and displays the PluginManagerWindow.
    Can be called in-process by Caster voice commands or hooks.
    """
    _ = get_or_create_app()
    window = PluginManagerWindow(registry=registry)
    window.show()
    window.raise_()
    window.activateWindow()
    return window


def main():
    """CLI entry point for running the Plugin Manager GUI standalone."""
    app = get_or_create_app()
    window = PluginManagerWindow()
    window.show()
    sys.exit(app.exec_() if hasattr(app, "exec_") else app.exec())


if __name__ == "__main__":
    main()
