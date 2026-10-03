# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Unit and integration test suite for Caster Plugin Manager core headless engine.
"""

from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
import threading
import unittest

from plugins.plugin_manager.core.models import (
    PluginHealthState,
    PluginMetadata,
    PluginRecord,
)
from plugins.plugin_manager.core.registry import PluginRegistry
from plugins.plugin_manager.core.scanner import PluginScanner, parse_toml_bytes
from plugins.plugin_manager.core.storage import LocalJsonStateAdapter
from plugins.plugin_manager.core.validator import PluginValidator


class TestPluginManagerModels(unittest.TestCase):
    """Tests for PluginMetadata and PluginRecord data structures."""

    def test_metadata_immutability(self):
        meta = PluginMetadata(
            name="test_plugin",
            version="1.0.0",
            description="Test Description",
            author="Author",
        )
        self.assertEqual(meta.name, "test_plugin")
        self.assertEqual(meta.version, "1.0.0")

        with self.assertRaises(FrozenInstanceError):
            meta.name = "mutated"  # type: ignore[misc]

    def test_record_serialization(self):
        meta = PluginMetadata(
            name="demo_plugin",
            version="2.1.0",
            description="Demo Description",
            author="Test Author",
            dependencies=["pytest"],
            platforms=["windows", "linux"],
        )
        record = PluginRecord(
            metadata=meta,
            enabled=True,
            health=PluginHealthState.READY,
        )
        data = record.to_dict()
        self.assertEqual(data["name"], "demo_plugin")
        self.assertEqual(data["version"], "2.1.0")
        self.assertTrue(data["enabled"])
        self.assertEqual(data["health"], "ready")
        self.assertEqual(data["dependencies"], ["pytest"])
        self.assertEqual(data["platforms"], ["windows", "linux"])


class TestPluginScanner(unittest.TestCase):
    """Tests for filesystem scanning and TOML parsing with fault containment."""

    def test_parse_toml_bytes(self):
        content = b"""
name = "sample"
version = "1.2.3"
description = "A sample plugin"
dependencies = ["PySide2", "requests"]
platforms = ["windows"]
"""
        parsed = parse_toml_bytes(content)
        self.assertEqual(parsed["name"], "sample")
        self.assertEqual(parsed["version"], "1.2.3")
        self.assertEqual(parsed["dependencies"], ["PySide2", "requests"])
        self.assertEqual(parsed["platforms"], ["windows"])

    def test_scan_existing_repository_plugins(self):
        scanner = PluginScanner()
        records = scanner.scan_all()

        self.assertIn("adce", records)
        self.assertIn("taskbar_hud", records)
        self.assertIn("themed_hud", records)
        self.assertIn("plugin_manager", records)

        themed_hud = records["themed_hud"]
        self.assertEqual(themed_hud.metadata.name, "themed_hud")
        self.assertIn("PySide2", themed_hud.metadata.dependencies)

    def test_scanner_malformed_metadata_containment(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)

            # 1. Healthy plugin
            valid_dir = base / "valid_plugin"
            valid_dir.mkdir()
            (valid_dir / "metadata.toml").write_text(
                'name = "valid_plugin"\nversion = "1.0.0"\ndescription = "Valid"\n',
                encoding="utf-8",
            )

            # 2. Corrupted TOML plugin
            invalid_dir = base / "broken_plugin"
            invalid_dir.mkdir()
            (invalid_dir / "metadata.toml").write_text(
                'name = "broken\nversion = [unclosed syntax',
                encoding="utf-8",
            )

            scanner = PluginScanner(search_dirs=[base])
            records = scanner.scan_all()

            # Scanner should discover both without raising
            self.assertIn("valid_plugin", records)
            self.assertIn("broken_plugin", records)

            self.assertEqual(records["valid_plugin"].health, PluginHealthState.READY)
            self.assertEqual(records["broken_plugin"].health, PluginHealthState.MALFORMED_METADATA)
            self.assertIsNotNone(records["broken_plugin"].diagnostic_message)


class TestPluginValidator(unittest.TestCase):
    """Tests for platform compatibility and dependency checking."""

    def test_platform_supported(self):
        validator = PluginValidator(target_platform="windows")

        win_meta = PluginMetadata(
            name="win_only",
            version="1.0.0",
            description="",
            platforms=["windows"],
        )
        self.assertTrue(validator.is_platform_supported(win_meta))

        linux_meta = PluginMetadata(
            name="linux_only",
            version="1.0.0",
            description="",
            platforms=["linux"],
        )
        self.assertFalse(validator.is_platform_supported(linux_meta))

    def test_dependency_checking(self):
        validator = PluginValidator()
        self.assertTrue(validator.check_dependency("pytest"))
        self.assertFalse(validator.check_dependency("non_existent_fake_package_12345"))

    def test_validate_record_lifecycle(self):
        validator = PluginValidator(target_platform="windows")

        # Incompatible platform
        meta_incompatible = PluginMetadata(
            name="linux_app",
            version="1.0.0",
            description="",
            platforms=["linux"],
        )
        rec = PluginRecord(metadata=meta_incompatible, enabled=True)
        validator.validate_record(rec)
        self.assertEqual(rec.health, PluginHealthState.INCOMPATIBLE_PLATFORM)

        # Missing dependency
        meta_missing_dep = PluginMetadata(
            name="dep_app",
            version="1.0.0",
            description="",
            platforms=["windows"],
            dependencies=["fake_lib_xyz"],
        )
        rec2 = PluginRecord(metadata=meta_missing_dep, enabled=True)
        validator.validate_record(rec2)
        self.assertEqual(rec2.health, PluginHealthState.MISSING_DEPENDENCIES)
        self.assertIn("fake_lib_xyz", rec2.missing_dependencies)

        # Healthy disabled vs enabled
        meta_ok = PluginMetadata(
            name="ok_app",
            version="1.0.0",
            description="",
            platforms=["windows"],
            dependencies=["pytest"],
        )
        rec3 = PluginRecord(metadata=meta_ok, enabled=False)
        validator.validate_record(rec3)
        self.assertEqual(rec3.health, PluginHealthState.DISABLED)

        rec3.enabled = True
        validator.validate_record(rec3)
        self.assertEqual(rec3.health, PluginHealthState.READY)


class TestLocalStorageAdapter(unittest.TestCase):
    """Tests for thread-safe atomic file storage adapter."""

    def test_atomic_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store_path = Path(tmp_dir) / "sub" / "plugin_states.json"
            adapter = LocalJsonStateAdapter(file_path=store_path)

            self.assertEqual(adapter.load_state(), {})

            test_state = {"themed_hud": True, "adce": False}
            adapter.save_state(test_state)

            loaded = adapter.load_state()
            self.assertEqual(loaded, test_state)
            self.assertTrue(store_path.exists())

    def test_corrupted_file_recovery(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store_path = Path(tmp_dir) / "corrupt.json"
            store_path.write_text("{invalid json format: ", encoding="utf-8")

            adapter = LocalJsonStateAdapter(file_path=store_path)
            self.assertEqual(adapter.load_state(), {})


class TestPluginRegistryController(unittest.TestCase):
    """Tests for unified PluginRegistry controller API."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.store_path = Path(self.tmp_dir.name) / "states.json"
        self.storage = LocalJsonStateAdapter(file_path=self.store_path)
        self.registry = PluginRegistry(storage=self.storage)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_scan_and_get_plugin(self):
        plugins = self.registry.scan()
        self.assertIn("themed_hud", plugins)

        record = self.registry.get_plugin("themed_hud")
        self.assertIsNotNone(record)
        self.assertEqual(record.metadata.name, "themed_hud")

    def test_set_enabled_and_persist(self):
        self.registry.scan()
        record = self.registry.set_enabled("themed_hud", True)
        self.assertTrue(record.enabled)

        # Verify persisted on disk
        stored = self.storage.load_state()
        self.assertTrue(stored.get("themed_hud"))

        # Verify new registry instance reloads state
        new_reg = PluginRegistry(storage=self.storage)
        reloaded_record = new_reg.get_plugin("themed_hud")
        self.assertIsNotNone(reloaded_record)
        self.assertTrue(reloaded_record.enabled)

    def test_set_enabled_non_existent_raises(self):
        with self.assertRaises(KeyError):
            self.registry.set_enabled("non_existent_plugin_name", True)

    def test_export_records(self):
        exported = self.registry.export_records()
        self.assertIsInstance(exported, list)
        self.assertGreater(len(exported), 0)
        names = [entry["name"] for entry in exported]
        self.assertIn("adce", names)
        self.assertIn("themed_hud", names)

    def test_thread_safe_concurrent_toggles(self):
        self.registry.scan()
        errors = []

        def worker(plugin_name: str, state: bool):
            try:
                for _ in range(10):
                    self.registry.set_enabled(plugin_name, state)
            except Exception as ex:
                errors.append(ex)

        threads = []
        for i in range(10):
            t1 = threading.Thread(target=worker, args=("themed_hud", i % 2 == 0))
            t2 = threading.Thread(target=worker, args=("adce", i % 2 != 0))
            threads.extend([t1, t2])

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertTrue(self.store_path.exists())


if __name__ == "__main__":
    unittest.main()
