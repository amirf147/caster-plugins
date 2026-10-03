# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Manifest resolver and remote version audit tracker for Caster plugins.
Compares locally installed plugin records against remote or cached manifest descriptors.
"""

import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, Optional, Tuple, Union
import urllib.request

from .models import PluginRecord

_logger = logging.getLogger("caster.plugins.plugin_manager.manifest")

DEFAULT_MANIFEST_URL = "https://raw.githubusercontent.com/amirf147/caster-plugins/master/manifest.json"


def parse_version_tuple(v_str: str) -> Tuple[int, ...]:
    """Converts standard semantic version string into integer tuple for comparison."""
    cleaned = re.sub(r"[^\d.]", "", str(v_str)).strip(".")
    if not cleaned:
        return (0, 0, 0)
    try:
        return tuple(int(part) for part in cleaned.split("."))
    except ValueError:
        return (0, 0, 0)


class ManifestResolver:
    """
    Loads repository manifests and audits plugin versions for update availability.
    """

    def __init__(
        self,
        manifest_path: Optional[Union[str, Path]] = None,
        remote_url: str = DEFAULT_MANIFEST_URL,
    ):
        if manifest_path is None:
            # Check if manifest.json exists in repo root
            current_file = Path(__file__).resolve()
            possible_manifest = current_file.parents[3] / "manifest.json"
            self._manifest_path = possible_manifest if possible_manifest.exists() else None
        else:
            self._manifest_path = Path(manifest_path).resolve() if manifest_path else None

        self._remote_url = remote_url
        self._cached_manifest: Optional[Dict[str, Any]] = None

    @property
    def manifest_path(self) -> Optional[Path]:
        return self._manifest_path

    @property
    def remote_url(self) -> str:
        return self._remote_url

    def load_manifest(self, force_refresh: bool = False, timeout_seconds: float = 3.0) -> Dict[str, Any]:
        """
        Loads manifest dictionary from local file or remote endpoint.
        """
        if self._cached_manifest is not None and not force_refresh:
            return dict(self._cached_manifest)

        # 1. Try local manifest file first if present
        if self._manifest_path and self._manifest_path.exists():
            try:
                content = self._manifest_path.read_text(encoding="utf-8")
                data = json.loads(content)
                if isinstance(data, dict) and "plugins" in data:
                    self._cached_manifest = data
                    return dict(data)
            except Exception as ex:
                _logger.debug("Failed to read local manifest file %s: %s", self._manifest_path, ex)

        # 2. Try remote URL fetch if local is absent or force refresh requested
        if self._remote_url:
            try:
                req = urllib.request.Request(
                    self._remote_url,
                    headers={"User-Agent": "CasterPluginManager/1.0"},
                )
                with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                    if resp.status == 200:
                        content = resp.read().decode("utf-8")
                        data = json.loads(content)
                        if isinstance(data, dict) and "plugins" in data:
                            self._cached_manifest = data
                            return dict(data)
            except Exception as ex:
                _logger.debug("Remote manifest fetch failed from %s: %s", self._remote_url, ex)

        return {"version": 1, "plugins": {}}

    def get_plugin_manifest_entry(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Retrieves manifest entry dictionary for a specific plugin name."""
        manifest = self.load_manifest()
        plugins = manifest.get("plugins", {})
        return plugins.get(plugin_name)

    def check_updates(self, records: Dict[str, PluginRecord]) -> Dict[str, Dict[str, Any]]:
        """
        Compares installed records against manifest entries.
        """
        manifest = self.load_manifest()
        manifest_plugins = manifest.get("plugins", {})

        audit: Dict[str, Dict[str, Any]] = {}
        for name, record in records.items():
            entry = manifest_plugins.get(name)
            installed_ver = record.metadata.version
            if not entry:
                audit[name] = {
                    "installed_version": installed_ver,
                    "latest_version": installed_ver,
                    "update_available": False,
                    "in_manifest": False,
                }
                continue

            latest_ver = entry.get("version", installed_ver)
            v_inst = parse_version_tuple(installed_ver)
            v_lat = parse_version_tuple(latest_ver)

            update_available = v_lat > v_inst
            audit[name] = {
                "installed_version": installed_ver,
                "latest_version": latest_ver,
                "update_available": update_available,
                "in_manifest": True,
                "description": entry.get("description", record.metadata.description),
            }

        return audit
