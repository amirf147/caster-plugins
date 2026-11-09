# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Unit tests for CasterTomlStateAdapter and CasterTomlConfigStore format-preserving TOML persistence.
"""

from pathlib import Path
import tempfile
import unittest

import tomlkit

from plugins.plugin_manager.core.config_store import CasterTomlConfigStore
from plugins.plugin_manager.core.options import OptionDefinition, OptionType
from plugins.plugin_manager.core.registry import PluginRegistry
from plugins.plugin_manager.core.storage import (
    CasterTomlStateAdapter,
    SettingsTomlStore,
)


class TestCasterTomlStorage(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self._temp_dir.name)
        self.settings_file = self.temp_path / "settings.toml"

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_state_adapter_read_and_write(self):
        initial_content = """# Caster settings file
[engine]
Engine = "Dragonfly"

[plugins]
# Active plugins
taskbar_hud = true
adce = false

[plugins.themed_hud]
enabled = true
theme = "classic"
"""
        self.settings_file.write_text(initial_content, encoding="utf-8")
        adapter = CasterTomlStateAdapter(file_path=self.settings_file)

        # 1. Verify read
        state = adapter.load_state()
        self.assertEqual(state["taskbar_hud"], True)
        self.assertEqual(state["adce"], False)
        self.assertEqual(state["themed_hud"], True)

        # 2. Mutate state and save
        state["adce"] = True
        state["themed_hud"] = False
        adapter.save_state(state)

        # 3. Verify format preservation in file
        updated_content = self.settings_file.read_text(encoding="utf-8")
        self.assertIn('[engine]', updated_content)
        self.assertIn('Engine = "Dragonfly"', updated_content)
        self.assertIn('# Active plugins', updated_content)

        doc = tomlkit.parse(updated_content)
        self.assertEqual(doc["plugins"]["adce"], True)
        self.assertEqual(doc["plugins"]["themed_hud"]["enabled"], False)
        self.assertEqual(doc["plugins"]["themed_hud"]["theme"], "classic")

    def test_state_adapter_creates_file_if_missing(self):
        missing_file = self.temp_path / "new_settings.toml"
        adapter = CasterTomlStateAdapter(file_path=missing_file)
        self.assertEqual(adapter.load_state(), {})

        adapter.save_state({"my_plugin": True, "other_plugin": False})
        self.assertTrue(missing_file.exists())
        loaded = adapter.load_state()
        self.assertEqual(loaded["my_plugin"], True)
        self.assertEqual(loaded["other_plugin"], False)

    def test_config_store_get_and_set(self):
        initial_content = """[plugins]
taskbar_hud = true

[plugins.themed_hud]
enabled = true
theme = "frosted-dark"
opacity = 0.8
"""
        self.settings_file.write_text(initial_content, encoding="utf-8")
        config_store = CasterTomlConfigStore(file_path=self.settings_file)

        defs = {
            "theme": OptionDefinition(
                name="theme",
                option_type=OptionType.CHOICE,
                default="classic",
                choices=["classic", "frosted-dark", "high-contrast"],
            ),
            "opacity": OptionDefinition(
                name="opacity",
                option_type=OptionType.FLOAT,
                default=1.0,
                min_value=0.1,
                max_value=1.0,
            ),
            "port": OptionDefinition(
                name="port",
                option_type=OptionType.INT,
                default=8339,
                min_value=1024,
                max_value=65535,
            ),
        }

        # 1. Read existing config merged with schema defaults
        config = config_store.get_plugin_config("themed_hud", defs)
        self.assertEqual(config["theme"], "frosted-dark")
        self.assertEqual(config["opacity"], 0.8)
        self.assertEqual(config["port"], 8339)

        # 2. Update config
        updated = config_store.set_plugin_config(
            "themed_hud",
            {"theme": "high-contrast", "opacity": 0.95, "port": 9000},
            defs,
        )
        self.assertEqual(updated["theme"], "high-contrast")
        self.assertEqual(updated["opacity"], 0.95)
        self.assertEqual(updated["port"], 9000)

        # 3. Verify settings.toml preserved enabled flag and updated table
        doc = tomlkit.parse(self.settings_file.read_text(encoding="utf-8"))
        self.assertEqual(doc["plugins"]["themed_hud"]["enabled"], True)
        self.assertEqual(doc["plugins"]["themed_hud"]["theme"], "high-contrast")
        self.assertEqual(doc["plugins"]["themed_hud"]["opacity"], 0.95)
        self.assertEqual(doc["plugins"]["themed_hud"]["port"], 9000)

    def test_config_store_validation_error(self):
        config_store = CasterTomlConfigStore(file_path=self.settings_file)
        defs = {
            "opacity": OptionDefinition(
                name="opacity",
                option_type=OptionType.FLOAT,
                default=1.0,
                min_value=0.1,
                max_value=1.0,
            )
        }

        with self.assertRaises(ValueError):
            config_store.set_plugin_config("themed_hud", {"opacity": 1.5}, defs)

    def test_config_store_reset_to_defaults(self):
        initial_content = """[plugins.themed_hud]
enabled = true
theme = "frosted-dark"
"""
        self.settings_file.write_text(initial_content, encoding="utf-8")
        config_store = CasterTomlConfigStore(file_path=self.settings_file)

        defs = {
            "theme": OptionDefinition(
                name="theme",
                option_type=OptionType.CHOICE,
                default="classic",
                choices=["classic", "frosted-dark"],
            )
        }

        reset_config = config_store.reset_plugin_config("themed_hud", defs)
        self.assertEqual(reset_config["theme"], "classic")

        # Verify enabled state was preserved in settings.toml
        adapter = CasterTomlStateAdapter(file_path=self.settings_file)
        self.assertEqual(adapter.load_state()["themed_hud"], True)

    def test_registry_integration_with_toml_persistence(self):
        plugin_dir = self.temp_path / "plugins" / "sample_plugin"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "metadata.toml").write_text(
            """name = "sample_plugin"
version = "1.0.0"
description = "Sample plugin"

[options.volume]
type = "int"
default = 50
min = 0
max = 100
""",
            encoding="utf-8",
        )

        storage = CasterTomlStateAdapter(file_path=self.settings_file)
        config_store = CasterTomlConfigStore(file_path=self.settings_file)

        registry = PluginRegistry(
            search_dirs=[self.temp_path / "plugins"],
            storage=storage,
            config_store=config_store,
        )

        records = registry.scan()
        self.assertIn("sample_plugin", records)
        self.assertFalse(records["sample_plugin"].enabled)

        # Enable plugin
        updated_rec = registry.set_enabled("sample_plugin", True)
        self.assertTrue(updated_rec.enabled)

        # Configure plugin
        cfg = registry.set_plugin_config("sample_plugin", {"volume": 75})
        self.assertEqual(cfg["volume"], 75)

        # Re-scan from disk
        fresh_registry = PluginRegistry(
            search_dirs=[self.temp_path / "plugins"],
            storage=storage,
            config_store=config_store,
        )
        fresh_records = fresh_registry.scan()
        self.assertTrue(fresh_records["sample_plugin"].enabled)
        self.assertEqual(fresh_registry.get_plugin_config("sample_plugin")["volume"], 75)

    def test_shared_lock_across_instances(self):
        """Verifies that all storage and config store adapters for a path share the identical RLock."""
        store1 = SettingsTomlStore(file_path=self.settings_file)
        store2 = SettingsTomlStore(file_path=self.settings_file)
        adapter = CasterTomlStateAdapter(file_path=self.settings_file)
        config = CasterTomlConfigStore(file_path=self.settings_file)

        self.assertIs(store1._lock, store2._lock)
        self.assertIs(store1._lock, adapter._lock)
        self.assertIs(store1._lock, config._lock)

    def test_table_and_scalar_format_consistency_no_corruption(self):
        """Verifies that save_state and config operations never corrupt tables or scalar booleans."""
        initial_content = """[plugins]
taskbar_hud = true

[plugins.themed_hud]
enabled = true
theme = "frosted-dark"
opacity = 0.8
"""
        self.settings_file.write_text(initial_content, encoding="utf-8")
        store = SettingsTomlStore(file_path=self.settings_file)

        defs = {
            "theme": OptionDefinition("theme", OptionType.CHOICE, default="classic", choices=["classic", "frosted-dark"]),
            "opacity": OptionDefinition("opacity", OptionType.FLOAT, default=1.0, min_value=0.1, max_value=1.0),
        }

        # 1. State save must preserve table and option values
        store.save_state({"taskbar_hud": False, "themed_hud": True})
        doc = tomlkit.parse(self.settings_file.read_text(encoding="utf-8"))
        self.assertIs(doc["plugins"]["taskbar_hud"], False)
        self.assertEqual(doc["plugins"]["themed_hud"]["theme"], "frosted-dark")
        self.assertEqual(doc["plugins"]["themed_hud"]["opacity"], 0.8)
        self.assertIs(doc["plugins"]["themed_hud"]["enabled"], True)

        # 2. Reset config must remove options but preserve enabled state in table
        store.reset_plugin_config("themed_hud", defs)
        doc2 = tomlkit.parse(self.settings_file.read_text(encoding="utf-8"))
        self.assertIs(doc2["plugins"]["themed_hud"]["enabled"], True)
        self.assertNotIn("theme", doc2["plugins"]["themed_hud"])
        self.assertNotIn("opacity", doc2["plugins"]["themed_hud"])

        # 3. Setting config on scalar boolean must convert to table preserving enabled value
        taskbar_defs = {
            "position": OptionDefinition("position", OptionType.STRING, default="top"),
        }
        store.set_plugin_config("taskbar_hud", {"position": "bottom"}, taskbar_defs)
        doc3 = tomlkit.parse(self.settings_file.read_text(encoding="utf-8"))
        self.assertIs(doc3["plugins"]["taskbar_hud"]["enabled"], False)
        self.assertEqual(doc3["plugins"]["taskbar_hud"]["position"], "bottom")

    def test_registry_default_uses_single_unified_store(self):
        """Verifies that default PluginRegistry shares a single SettingsTomlStore for storage and options."""
        registry = PluginRegistry()
        self.assertIs(registry.storage, registry.config_store)
        self.assertIsInstance(registry.storage, SettingsTomlStore)


if __name__ == "__main__":
    unittest.main()
