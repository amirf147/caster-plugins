# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Automated unit tests for Caster Plugin Manager GUI components.
Runs in offscreen Qt mode.
"""

import os
from pathlib import Path
import tempfile
import unittest

# Ensure Qt runs offscreen in headless test environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from PySide2 import QtCore, QtGui, QtWidgets
    from PySide2.QtTest import QTest
    HAS_QT = True
except ImportError:
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets  # noqa: F401
        from PyQt5.QtTest import QTest
        HAS_QT = True
    except ImportError:
        HAS_QT = False

if HAS_QT:
    from plugins.plugin_manager.core.models import (
        PluginHealthState,
        PluginMetadata,
        PluginRecord,
    )
    from plugins.plugin_manager.core.registry import PluginRegistry
    from plugins.plugin_manager.core.storage import LocalJsonStateAdapter
    from plugins.plugin_manager.gui.runner import get_or_create_app
    from plugins.plugin_manager.gui.widgets.detail_pane import DetailPane
    from plugins.plugin_manager.gui.widgets.plugin_row import PluginRowWidget
    from plugins.plugin_manager.gui.window import PluginManagerWindow


@unittest.skipUnless(HAS_QT, "Qt bindings (PySide2/PyQt5) not available in environment")
class TestPluginManagerGui(unittest.TestCase):
    """Headless Qt tests for Plugin Manager GUI widgets and windows."""

    @classmethod
    def setUpClass(cls):
        cls.app = get_or_create_app()

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmp_dir.name) / "states.json"
        self.storage = LocalJsonStateAdapter(file_path=self.store_path)
        self.registry = PluginRegistry(storage=self.storage)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_plugin_row_widget_rendering(self):
        meta = PluginMetadata(
            name="test_hud",
            version="1.0.0",
            description="Test HUD Plugin",
            author="Developer",
        )
        rec = PluginRecord(metadata=meta, enabled=False, health=PluginHealthState.DISABLED)
        widget = PluginRowWidget(rec)

        self.assertEqual(widget._name_label.text(), "test_hud")
        self.assertEqual(widget._version_label.text(), "v1.0.0")
        self.assertEqual(widget._toggle_btn.text(), "Disabled")
        self.assertTrue(widget._toggle_btn.isEnabled())

        # Test toggle signal emission
        emitted = []
        widget.toggled.connect(lambda name, state: emitted.append((name, state)))
        widget._toggle_btn.click()

        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0], ("test_hud", True))

    def test_plugin_row_widget_unavailable_state(self):
        meta = PluginMetadata(name="broken_plugin", version="0.1.0", description="Broken")
        rec = PluginRecord(
            metadata=meta,
            enabled=False,
            health=PluginHealthState.MISSING_DEPENDENCIES,
            diagnostic_message="Missing lib",
        )
        widget = PluginRowWidget(rec)

        self.assertEqual(widget._toggle_btn.text(), "Unavailable")
        self.assertFalse(widget._toggle_btn.isEnabled())

    def test_detail_pane_population_and_clear(self):
        pane = DetailPane()
        meta = PluginMetadata(
            name="detail_test",
            version="2.0.0",
            description="Detailed test description",
            author="Author Name",
            platforms=["windows"],
            dependencies=["PySide2"],
            entry_point="plugin.py:Plugin",
            plugin_dir=Path(self.tmp_dir.name),
        )
        rec = PluginRecord(
            metadata=meta,
            enabled=True,
            health=PluginHealthState.READY,
            diagnostic_message="Sample diagnostic note",
        )

        pane.set_plugin(rec)
        self.assertEqual(pane._title_label.text(), "detail_test")
        self.assertIn("Author Name", pane._meta_subhead.text())
        self.assertEqual(pane._platforms_val.text(), "windows")
        self.assertEqual(pane._deps_val.text(), "PySide2")
        self.assertFalse(pane._diag_frame.isHidden())
        self.assertEqual(pane._diag_text.text(), "Sample diagnostic note")

        pane.clear()
        self.assertEqual(pane._title_label.text(), "Select a plugin")
        self.assertTrue(pane._diag_frame.isHidden())

    def test_window_list_population_and_filtering(self):
        window = PluginManagerWindow(registry=self.registry)

        # Asserts discovered repo plugins are listed
        list_widget = window._list_widget
        self.assertGreaterEqual(list_widget.count(), 4)

        # Test search filter
        window._search_input.setText("themed")
        self.assertEqual(list_widget.count(), 1)
        first_item = list_widget.item(0)
        self.assertEqual(first_item.data(QtCore.Qt.UserRole), "themed_hud")

        # Test detail pane updated on selection
        self.assertEqual(window._detail_pane._title_label.text(), "themed_hud")

        # Clear filter
        window._search_input.setText("")
        self.assertGreaterEqual(list_widget.count(), 4)

    def test_window_toggle_persists_state(self):
        window = PluginManagerWindow(registry=self.registry)

        # Trigger toggle on themed_hud
        window._on_plugin_toggled("themed_hud", True)

        # Check in memory and on disk
        rec = self.registry.get_plugin("themed_hud")
        self.assertIsNotNone(rec)
        self.assertTrue(rec.enabled)

        disk_state = self.storage.load_state()
        self.assertTrue(disk_state.get("themed_hud"))

        # Verify footer updated
        self.assertIn("Enabled: 1", window._footer_label.text())

    def test_window_keyboard_shortcuts(self):
        window = PluginManagerWindow(registry=self.registry)
        window.show()

        # Test Escape key closes window
        QTest.keyClick(window, QtCore.Qt.Key_Escape)
        self.assertFalse(window.isVisible())


if __name__ == "__main__":
    unittest.main()
