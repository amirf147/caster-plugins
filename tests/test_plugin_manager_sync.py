# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Unit tests for PluginSyncEngine cross-platform file synchronization.
"""

from pathlib import Path
import tempfile
import unittest

from plugins.plugin_manager.core.sync import PluginSyncEngine


class TestPluginSyncEngine(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self._temp_dir.name)
        self.source_dir = self.temp_path / "source_plugins"
        self.target_dir = self.temp_path / "target_plugins"

        self.source_dir.mkdir()
        self.target_dir.mkdir()

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_discover_source_plugins(self):
        (self.source_dir / "plugin_a").mkdir()
        (self.source_dir / "plugin_a" / "metadata.toml").write_text('name = "plugin_a"\n', encoding="utf-8")

        (self.source_dir / "plugin_b").mkdir()
        (self.source_dir / "plugin_b" / "plugin.py").write_text('# plugin b\n', encoding="utf-8")

        (self.source_dir / ".hidden_folder").mkdir()
        (self.source_dir / "__pycache__").mkdir()

        engine = PluginSyncEngine(source_dir=self.source_dir, target_dir=self.target_dir)
        discovered = engine.discover_source_plugins()
        self.assertEqual(discovered, ["plugin_a", "plugin_b"])

    def test_drift_detection_and_sync(self):
        p_src = self.source_dir / "my_plugin"
        p_src.mkdir()
        (p_src / "metadata.toml").write_text('name = "my_plugin"\nversion = "1.0.0"\n', encoding="utf-8")
        (p_src / "plugin.py").write_text('print("v1")\n', encoding="utf-8")

        engine = PluginSyncEngine(source_dir=self.source_dir, target_dir=self.target_dir)

        # 1. Target does not have the plugin
        drift = engine.get_plugin_drift("my_plugin")
        self.assertEqual(drift["status"], "missing_in_target")
        self.assertEqual(len(drift["added_files"]), 2)

        # 2. Sync to target
        res = engine.sync_plugin("my_plugin")
        self.assertEqual(len(res["copied"]), 2)
        self.assertEqual(res["deleted"], [])

        # 3. Target is now synced
        drift_after = engine.get_plugin_drift("my_plugin")
        self.assertEqual(drift_after["status"], "synced")
        self.assertEqual(len(drift_after["unchanged_files"]), 2)

        # 4. Modify source file
        (p_src / "plugin.py").write_text('print("v2 updated")\n', encoding="utf-8")
        drift_mod = engine.get_plugin_drift("my_plugin")
        self.assertEqual(drift_mod["status"], "drifted")
        self.assertIn("plugin.py", drift_mod["modified_files"])

        # 5. Add a stale file in target
        (self.target_dir / "my_plugin" / "old_stale.txt").write_text("obsolete", encoding="utf-8")
        drift_stale = engine.get_plugin_drift("my_plugin")
        self.assertIn("old_stale.txt", drift_stale["stale_files"])

        # 6. Re-sync with pruning
        res2 = engine.sync_plugin("my_plugin", prune_stale=True)
        self.assertIn("plugin.py", res2["copied"])
        self.assertIn("old_stale.txt", res2["deleted"])
        self.assertFalse((self.target_dir / "my_plugin" / "old_stale.txt").exists())

    def test_dry_run_does_not_modify_disk(self):
        p_src = self.source_dir / "plugin_c"
        p_src.mkdir()
        (p_src / "metadata.toml").write_text('name = "plugin_c"\n', encoding="utf-8")

        engine = PluginSyncEngine(source_dir=self.source_dir, target_dir=self.target_dir)
        res = engine.sync_plugin("plugin_c", dry_run=True)
        self.assertTrue(res["dry_run"])
        self.assertEqual(res["copied"], ["metadata.toml"])
        self.assertFalse((self.target_dir / "plugin_c").exists())

    def test_resolve_local_source_dir_heuristics(self):
        """Verifies repository discovery heuristics across environment and settings."""
        import os
        custom_repo = self.temp_path / "custom_repo" / "plugins"
        custom_repo.mkdir(parents=True)

        # 1. Environment variable override
        old_env = os.environ.get("CASTER_PLUGINS_REPO")
        try:
            os.environ["CASTER_PLUGINS_REPO"] = str(custom_repo.parent)
            resolved = PluginSyncEngine.resolve_local_source_dir(target_dir=self.target_dir)
            self.assertEqual(resolved, custom_repo.resolve())
        finally:
            if old_env is not None:
                os.environ["CASTER_PLUGINS_REPO"] = old_env
            else:
                os.environ.pop("CASTER_PLUGINS_REPO", None)

        # 2. Target exclusion check (should not resolve to target_dir itself)
        try:
            os.environ["CASTER_PLUGINS_REPO"] = str(self.target_dir)
            resolved_target = PluginSyncEngine.resolve_local_source_dir(target_dir=self.target_dir)
            self.assertNotEqual(resolved_target, self.target_dir.resolve())
        finally:
            if old_env is not None:
                os.environ["CASTER_PLUGINS_REPO"] = old_env
            else:
                os.environ.pop("CASTER_PLUGINS_REPO", None)

    def test_discover_target_and_prune_orphaned_plugins(self):
        """Verifies detection and pruning of plugins present in target but absent from source."""
        # Source has plugin_live
        p_src = self.source_dir / "plugin_live"
        p_src.mkdir()
        (p_src / "metadata.toml").write_text('name = "plugin_live"\n', encoding="utf-8")

        # Target has plugin_live and orphaned plugin_dead
        p_dst_live = self.target_dir / "plugin_live"
        p_dst_live.mkdir()
        (p_dst_live / "metadata.toml").write_text('name = "plugin_live"\n', encoding="utf-8")

        p_dst_dead = self.target_dir / "plugin_dead"
        p_dst_dead.mkdir()
        (p_dst_dead / "metadata.toml").write_text('name = "plugin_dead"\n', encoding="utf-8")
        (p_dst_dead / "plugin.py").write_text('# dead\n', encoding="utf-8")

        engine = PluginSyncEngine(source_dir=self.source_dir, target_dir=self.target_dir)

        target_plugins = engine.discover_target_plugins()
        self.assertEqual(sorted(target_plugins), ["plugin_dead", "plugin_live"])

        orphaned = engine.get_orphaned_plugins()
        self.assertEqual(orphaned, ["plugin_dead"])

        # Dry run
        dry_pruned = engine.prune_orphaned_plugins(dry_run=True)
        self.assertEqual(dry_pruned, ["plugin_dead"])
        self.assertTrue((self.target_dir / "plugin_dead").exists())

        # Actual prune
        pruned = engine.prune_orphaned_plugins(dry_run=False)
        self.assertEqual(pruned, ["plugin_dead"])
        self.assertFalse((self.target_dir / "plugin_dead").exists())
        self.assertTrue((self.target_dir / "plugin_live").exists())


if __name__ == "__main__":
    unittest.main()
