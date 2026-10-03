# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Automated unit tests for Plugin Options schema, validation, persistence, and dynamic Qt form.
"""

import os
from pathlib import Path
import tempfile
import unittest

os.environ["QT_QPA_PLATFORM"] = "offscreen"

try:
    from PySide2 import QtCore, QtWidgets
    HAS_QT = True
except ImportError:
    try:
        from PyQt5 import QtCore, QtWidgets  # noqa: F401
        HAS_QT = True
    except ImportError:
        HAS_QT = False

from plugins.plugin_manager.core.config_store import PluginConfigStore
from plugins.plugin_manager.core.options import (
    OptionDefinition,
    OptionType,
    validate_and_coerce,
)
from plugins.plugin_manager.core.registry import PluginRegistry
from plugins.plugin_manager.core.scanner import PluginScanner
from plugins.plugin_manager.core.storage import LocalJsonStateAdapter

if HAS_QT:
    from plugins.plugin_manager.gui.runner import get_or_create_app
    from plugins.plugin_manager.gui.widgets.settings_form import SettingsFormWidget
    from plugins.plugin_manager.gui.window import PluginManagerWindow


class TestPluginOptionsCore(unittest.TestCase):
    """Tests for OptionDefinition parsing, serialization, and validation."""

    def test_option_definition_from_dict(self):
        raw = {
            "type": "choice",
            "default": "dark",
            "description": "Theme choice",
            "choices": ["light", "dark"],
        }
        defn = OptionDefinition.from_dict("ui_theme", raw)
        self.assertEqual(defn.name, "ui_theme")
        self.assertEqual(defn.option_type, OptionType.CHOICE)
        self.assertEqual(defn.default, "dark")
        self.assertEqual(defn.choices, ["light", "dark"])

        data = defn.to_dict()
        self.assertEqual(data["name"], "ui_theme")
        self.assertEqual(data["type"], "choice")

    def test_validation_bool(self):
        defn = OptionDefinition("flag", OptionType.BOOL, default=False)
        valid, val, err = validate_and_coerce(defn, True)
        self.assertTrue(valid)
        self.assertTrue(val)

        valid, val, err = validate_and_coerce(defn, "yes")
        self.assertTrue(valid)
        self.assertTrue(val)

        valid, val, err = validate_and_coerce(defn, "invalid_val")
        self.assertFalse(valid)
        self.assertIsNotNone(err)

    def test_validation_int_and_float_bounds(self):
        defn_int = OptionDefinition("port", OptionType.INT, default=8000, min_value=1024, max_value=65535)
        self.assertTrue(validate_and_coerce(defn_int, 8080)[0])
        self.assertFalse(validate_and_coerce(defn_int, 80)[0])
        self.assertFalse(validate_and_coerce(defn_int, 70000)[0])
        self.assertFalse(validate_and_coerce(defn_int, "not_a_number")[0])

        defn_float = OptionDefinition("opacity", OptionType.FLOAT, default=1.0, min_value=0.0, max_value=1.0)
        self.assertTrue(validate_and_coerce(defn_float, 0.75)[0])
        self.assertFalse(validate_and_coerce(defn_float, 1.5)[0])

    def test_validation_choice(self):
        defn = OptionDefinition("theme", OptionType.CHOICE, default="classic", choices=["classic", "dark"])
        self.assertTrue(validate_and_coerce(defn, "dark")[0])
        self.assertFalse(validate_and_coerce(defn, "neon_cyberpunk")[0])


class TestPluginConfigStore(unittest.TestCase):
    """Tests for thread-safe config store persistence and schema defaults merging."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmp_dir.name) / "configs.json"
        self.config_store = PluginConfigStore(file_path=self.store_path)
        self.definitions = {
            "theme": OptionDefinition("theme", OptionType.CHOICE, default="classic", choices=["classic", "dark"]),
            "opacity": OptionDefinition("opacity", OptionType.FLOAT, default=1.0, min_value=0.1, max_value=1.0),
            "enabled_feature": OptionDefinition("enabled_feature", OptionType.BOOL, default=True),
        }

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_get_defaults_when_empty(self):
        config = self.config_store.get_plugin_config("sample_plugin", self.definitions)
        self.assertEqual(config["theme"], "classic")
        self.assertEqual(config["opacity"], 1.0)
        self.assertTrue(config["enabled_feature"])

    def test_set_valid_config_and_persist(self):
        updated = self.config_store.set_plugin_config(
            "sample_plugin",
            {"theme": "dark", "opacity": 0.85},
            self.definitions,
        )
        self.assertEqual(updated["theme"], "dark")
        self.assertEqual(updated["opacity"], 0.85)
        self.assertTrue(updated["enabled_feature"])  # Default maintained

        # Verify disk reloading
        new_store = PluginConfigStore(file_path=self.store_path)
        reloaded = new_store.get_plugin_config("sample_plugin", self.definitions)
        self.assertEqual(reloaded["theme"], "dark")
        self.assertEqual(reloaded["opacity"], 0.85)

    def test_set_invalid_config_raises(self):
        with self.assertRaises(ValueError):
            self.config_store.set_plugin_config(
                "sample_plugin",
                {"opacity": 5.0},  # Exceeds max 1.0
                self.definitions,
            )

    def test_reset_plugin_config(self):
        self.config_store.set_plugin_config(
            "sample_plugin",
            {"theme": "dark"},
            self.definitions,
        )
        reset = self.config_store.reset_plugin_config("sample_plugin", self.definitions)
        self.assertEqual(reset["theme"], "classic")


class TestScannerOptionsParsing(unittest.TestCase):
    """Tests that filesystem scanner extracts options from metadata.toml."""

    def test_scanner_extracts_themed_hud_options(self):
        scanner = PluginScanner()
        records = scanner.scan_all()
        self.assertIn("themed_hud", records)

        themed_hud = records["themed_hud"]
        options = themed_hud.metadata.options
        self.assertIn("theme", options)
        self.assertIn("opacity", options)
        self.assertIn("status_border", options)
        self.assertIn("port", options)

        self.assertEqual(options["theme"].option_type, OptionType.CHOICE)
        self.assertEqual(options["opacity"].option_type, OptionType.FLOAT)
        self.assertEqual(options["port"].option_type, OptionType.INT)


@unittest.skipUnless(HAS_QT, "Qt not available in environment")
class TestSettingsFormGui(unittest.TestCase):
    """Tests for dynamic SettingsFormWidget generation and window tabs."""

    @classmethod
    def setUpClass(cls):
        cls.app = get_or_create_app()

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmp_dir.name) / "configs.json"
        self.config_store = PluginConfigStore(file_path=self.store_path)
        self.registry = PluginRegistry(
            storage=LocalJsonStateAdapter(file_path=Path(self.tmp_dir.name) / "states.json"),
            config_store=self.config_store,
        )

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_settings_form_generation_and_saving(self):
        form = SettingsFormWidget(config_store=self.config_store)
        records = self.registry.scan()
        themed_rec = records.get("themed_hud")
        self.assertIsNotNone(themed_rec)

        form.set_plugin(themed_rec)

        # Verify controls generated for all options
        self.assertIn("theme", form._controls)
        self.assertIn("opacity", form._controls)
        self.assertIn("status_border", form._controls)

        # Trigger save
        saved_events = []
        form.config_saved.connect(lambda name, cfg: saved_events.append((name, cfg)))
        form._on_save_clicked()

        self.assertEqual(len(saved_events), 1)
        self.assertEqual(saved_events[0][0], "themed_hud")
        self.assertIn("theme", saved_events[0][1])

    def test_window_tab_switching_and_count(self):
        window = PluginManagerWindow(registry=self.registry)
        self.assertEqual(window._tabs.tabText(0), "Overview")

        # Select first item and verify Settings tab label
        window._on_list_selection_changed(
            window._list_widget.item(0), None
        )
        self.assertIn("Settings", window._tabs.tabText(1))


if __name__ == "__main__":
    unittest.main()
