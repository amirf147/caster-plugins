# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Filesystem scanner and metadata parser for Caster plugins.
Supports isolated TOML parsing and manifest reconciliation with per-directory fault containment.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]

from .models import PluginHealthState, PluginMetadata, PluginRecord
from .options import OptionDefinition

_logger = logging.getLogger("caster.plugins.plugin_manager.scanner")


def parse_toml_bytes(data: bytes) -> Dict[str, Any]:
    """Parses TOML bytes using available standard or bundled parser."""
    if tomllib is not None:
        return tomllib.loads(data.decode("utf-8"))

    # Minimal fallback parser for simple key-value TOML if tomli/tomllib unavailable
    result: Dict[str, Any] = {}
    for line in data.decode("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if val.startswith('"') and val.endswith('"'):
                result[key] = val[1:-1]
            elif val.startswith("'") and val.endswith("'"):
                result[key] = val[1:-1]
            elif val.startswith("[") and val.endswith("]"):
                inner = val[1:-1].strip()
                if not inner:
                    result[key] = []
                else:
                    items = [item.strip().strip('"').strip("'") for item in inner.split(",") if item.strip()]
                    result[key] = items
            elif val.lower() == "true":
                result[key] = True
            elif val.lower() == "false":
                result[key] = False
    return result


class PluginScanner:
    """
    Discovers installed Caster plugins across specified search directories.
    """

    def __init__(self, search_dirs: Optional[List[Union[str, Path]]] = None, manifest_path: Optional[Union[str, Path]] = None):
        if search_dirs is None:
            # Default to repo plugins directory relative to this file
            current_file = Path(__file__).resolve()
            plugins_root = current_file.parents[2]  # <repo>/plugins
            self._search_dirs = [plugins_root]
        else:
            self._search_dirs = [Path(p).resolve() for p in search_dirs]

        if manifest_path is None:
            # Check if manifest.json exists in repo root
            current_file = Path(__file__).resolve()
            possible_manifest = current_file.parents[3] / "manifest.json"
            self._manifest_path = possible_manifest if possible_manifest.exists() else None
        else:
            self._manifest_path = Path(manifest_path).resolve() if manifest_path else None

    @property
    def search_dirs(self) -> List[Path]:
        return list(self._search_dirs)

    def scan_directory(self, base_dir: Path) -> Dict[str, PluginRecord]:
        """
        Scans a single directory for subfolders containing plugin metadata.
        Faults in individual plugins are contained and do not interrupt the scan.
        """
        records: Dict[str, PluginRecord] = {}
        if not base_dir.exists() or not base_dir.is_dir():
            _logger.debug("Plugin search directory does not exist: %s", base_dir)
            return records

        for child in sorted(base_dir.iterdir()):
            if not child.is_dir() or child.name.startswith(".") or child.name.startswith("__"):
                continue

            metadata_file = child / "metadata.toml"
            if metadata_file.exists():
                name, record = self._parse_metadata_file(child, metadata_file)
                records[name] = record
            else:
                # Check if this directory is recognized by manifest.json
                manifest_record = self._match_manifest_entry(child)
                if manifest_record is not None:
                    records[manifest_record.metadata.name] = manifest_record

        return records

    def scan_all(self) -> Dict[str, PluginRecord]:
        """
        Scans all configured search directories and returns aggregated records.
        """
        all_records: Dict[str, PluginRecord] = {}
        for search_dir in self._search_dirs:
            dir_records = self.scan_directory(search_dir)
            all_records.update(dir_records)
        return all_records

    def _parse_metadata_file(self, plugin_dir: Path, metadata_file: Path) -> Tuple[str, PluginRecord]:
        """
        Parses a single metadata.toml file safely.
        """
        try:
            raw_bytes = metadata_file.read_bytes()
            data = parse_toml_bytes(raw_bytes)

            name = data.get("name", plugin_dir.name)
            version = data.get("version", "0.0.0")
            description = data.get("description", "")
            author = data.get("author", "")
            dependencies = data.get("dependencies", [])
            min_caster_version = data.get("min_caster_version")
            platforms = data.get("platforms", ["windows", "linux", "darwin"])
            entry_point = data.get("entry_point")

            # Parse [options] table
            raw_options = data.get("options", {})
            parsed_options: Dict[str, OptionDefinition] = {}
            if isinstance(raw_options, dict):
                for opt_name, opt_spec in raw_options.items():
                    if isinstance(opt_spec, dict):
                        parsed_options[opt_name] = OptionDefinition.from_dict(opt_name, opt_spec)

            metadata = PluginMetadata(
                name=name,
                version=version,
                description=description,
                author=author,
                dependencies=list(dependencies),
                min_caster_version=min_caster_version,
                platforms=list(platforms),
                entry_point=entry_point,
                plugin_dir=plugin_dir,
                options=parsed_options,
            )
            return name, PluginRecord(metadata=metadata, health=PluginHealthState.READY)

        except Exception as ex:
            _logger.warning("Failed to parse plugin metadata in %s: %s", plugin_dir, ex)
            fallback_metadata = PluginMetadata(
                name=plugin_dir.name,
                version="0.0.0",
                description="Malformed metadata descriptor",
                plugin_dir=plugin_dir,
            )
            return plugin_dir.name, PluginRecord(
                metadata=fallback_metadata,
                health=PluginHealthState.MALFORMED_METADATA,
                diagnostic_message="Metadata parse failure: {}".format(ex),
            )

    def _match_manifest_entry(self, plugin_dir: Path) -> Optional[PluginRecord]:
        """
        Attempts to construct a PluginRecord using manifest.json if present.
        """
        if not self._manifest_path or not self._manifest_path.exists():
            return None

        try:
            manifest_data = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            plugins_dict = manifest_data.get("plugins", {})
            entry = plugins_dict.get(plugin_dir.name)
            if not entry:
                return None

            raw_options = entry.get("options", {})
            parsed_options: Dict[str, OptionDefinition] = {}
            if isinstance(raw_options, dict):
                for opt_name, opt_spec in raw_options.items():
                    if isinstance(opt_spec, dict):
                        parsed_options[opt_name] = OptionDefinition.from_dict(opt_name, opt_spec)

            metadata = PluginMetadata(
                name=plugin_dir.name,
                version=entry.get("version", "0.0.0"),
                description=entry.get("description", ""),
                author=entry.get("author", ""),
                dependencies=list(entry.get("dependencies", [])),
                min_caster_version=entry.get("min_caster_version"),
                platforms=list(entry.get("platforms", ["windows", "linux", "darwin"])),
                entry_point=entry.get("entry_point"),
                plugin_dir=plugin_dir,
                options=parsed_options,
            )
            return PluginRecord(metadata=metadata, health=PluginHealthState.READY)
        except Exception as ex:
            _logger.debug("Failed to extract manifest record for %s: %s", plugin_dir, ex)
            return None
