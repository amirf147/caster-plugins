# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Unit tests for ManifestResolver and version audit tracker.
"""

import json
from pathlib import Path
import tempfile
import unittest

from plugins.plugin_manager.core.manifest import ManifestResolver, parse_version_tuple
from plugins.plugin_manager.core.models import PluginHealthState, PluginMetadata, PluginRecord


class TestManifestResolver(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self._temp_dir.name)
        self.manifest_file = self.temp_path / "manifest.json"

    def tearDown(self):
        self._temp_dir.cleanup()

    def test_parse_version_tuple(self):
        self.assertEqual(parse_version_tuple("1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version_tuple("v2.0.0"), (2, 0, 0))
        self.assertEqual(parse_version_tuple("1.0"), (1, 0))
        self.assertEqual(parse_version_tuple("invalid"), (0, 0, 0))

    def test_load_manifest_and_audit_updates(self):
        manifest_payload = {
            "version": 1,
            "plugins": {
                "themed_hud": {
                    "version": "2.1.0",
                    "description": "Updated HUD description",
                },
                "adce": {
                    "version": "1.0.0",
                    "description": "ADCE Client",
                },
            },
        }
        self.manifest_file.write_text(json.dumps(manifest_payload), encoding="utf-8")

        resolver = ManifestResolver(manifest_path=self.manifest_file)
        data = resolver.load_manifest()
        self.assertIn("themed_hud", data["plugins"])

        # Create installed records
        records = {
            "themed_hud": PluginRecord(
                metadata=PluginMetadata(name="themed_hud", version="2.0.0", description="HUD"),
                health=PluginHealthState.READY,
            ),
            "adce": PluginRecord(
                metadata=PluginMetadata(name="adce", version="1.0.0", description="ADCE"),
                health=PluginHealthState.READY,
            ),
            "custom_local": PluginRecord(
                metadata=PluginMetadata(name="custom_local", version="0.5.0", description="Local"),
                health=PluginHealthState.READY,
            ),
        }

        audit = resolver.check_updates(records)
        self.assertTrue(audit["themed_hud"]["update_available"])
        self.assertEqual(audit["themed_hud"]["latest_version"], "2.1.0")

        self.assertFalse(audit["adce"]["update_available"])
        self.assertEqual(audit["adce"]["latest_version"], "1.0.0")

        self.assertFalse(audit["custom_local"]["update_available"])
        self.assertFalse(audit["custom_local"]["in_manifest"])


if __name__ == "__main__":
    unittest.main()
