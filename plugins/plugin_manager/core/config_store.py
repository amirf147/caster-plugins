# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Thread-safe, atomic persistence store for plugin configuration parameters.
"""

import json
import logging
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Dict, Optional, Union

import tomlkit

from .options import OptionDefinition, validate_and_coerce
from .storage import resolve_caster_settings_path

_logger = logging.getLogger("caster.plugins.plugin_manager.config_store")


class CasterTomlConfigStore:
    """
    Manages loading, validating, and saving per-plugin configuration parameters
    directly within Caster's settings.toml file under [plugins.<name>].
    """

    def __init__(self, file_path: Optional[Union[str, Path]] = None):
        self._path = resolve_caster_settings_path(file_path)
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    def _read_doc(self) -> tomlkit.TOMLDocument:
        """Reads and parses the TOML document, returning an empty document on failure."""
        if not self._path.exists():
            return tomlkit.document()
        try:
            content = self._path.read_text(encoding="utf-8")
            if not content.strip():
                return tomlkit.document()
            return tomlkit.parse(content)
        except Exception as ex:
            _logger.warning("Failed to parse TOML configuration from %s: %s", self._path, ex)
            return tomlkit.document()

    def get_plugin_config(
        self, plugin_name: str, definitions: Dict[str, OptionDefinition]
    ) -> Dict[str, Any]:
        """
        Returns effective configuration dictionary for a plugin, merging stored TOML
        overrides over schema defaults.
        """
        with self._lock:
            doc = self._read_doc()
            plugins = doc.get("plugins")
            stored_opts: Dict[str, Any] = {}

            if isinstance(plugins, dict) and plugin_name in plugins:
                val = plugins[plugin_name]
                if isinstance(val, dict) or hasattr(val, "get"):
                    for k, v in val.items():
                        if k != "enabled":
                            stored_opts[k] = v

            effective: Dict[str, Any] = {}
            for opt_name, defn in definitions.items():
                if opt_name in stored_opts:
                    raw_val = stored_opts[opt_name]
                    is_valid, coerced_val, _ = validate_and_coerce(defn, raw_val)
                    if is_valid:
                        effective[opt_name] = coerced_val
                    else:
                        effective[opt_name] = defn.default
                else:
                    effective[opt_name] = defn.default

            return effective

    def set_plugin_config(
        self,
        plugin_name: str,
        config: Dict[str, Any],
        definitions: Dict[str, OptionDefinition],
    ) -> Dict[str, Any]:
        """
        Validates, applies, and atomically flushes configuration overrides to [plugins.<name>] in settings.toml.
        Raises ValueError if any configuration value fails validation.
        """
        with self._lock:
            # 1. Validate and coerce all provided option keys
            valid_overrides: Dict[str, Any] = {}
            for key, val in config.items():
                if key in definitions:
                    defn = definitions[key]
                    is_valid, coerced_val, err_msg = validate_and_coerce(defn, val)
                    if not is_valid:
                        raise ValueError(f"Invalid value for option '{key}': {err_msg}")
                    valid_overrides[key] = coerced_val

            # 2. Update TOML document
            doc = self._read_doc()
            if "plugins" not in doc or not isinstance(doc["plugins"], dict):
                doc["plugins"] = tomlkit.table()

            plugins_tbl = doc["plugins"]
            existing = plugins_tbl.get(plugin_name)

            if isinstance(existing, dict) or hasattr(existing, "get"):
                target_table = existing
            else:
                existing_enabled = bool(existing) if isinstance(existing, bool) else False
                target_table = tomlkit.table()
                target_table["enabled"] = existing_enabled
                plugins_tbl[plugin_name] = target_table

            for k, v in valid_overrides.items():
                target_table[k] = v

            self._atomic_write(doc)
            return self.get_plugin_config(plugin_name, definitions)

    def reset_plugin_config(
        self, plugin_name: str, definitions: Dict[str, OptionDefinition]
    ) -> Dict[str, Any]:
        """
        Removes saved option overrides for a plugin in settings.toml, reverting all options to schema defaults.
        """
        with self._lock:
            doc = self._read_doc()
            plugins = doc.get("plugins")
            if isinstance(plugins, dict) and plugin_name in plugins:
                existing = plugins[plugin_name]
                if isinstance(existing, dict) or hasattr(existing, "get"):
                    enabled_val = bool(existing.get("enabled", False))
                    plugins[plugin_name] = enabled_val
                    self._atomic_write(doc)

            return self.get_plugin_config(plugin_name, definitions)

    def _atomic_write(self, doc: tomlkit.TOMLDocument):
        """Atomically saves the TOML document to disk."""
        parent_dir = self._path.parent
        parent_dir.mkdir(parents=True, exist_ok=True)
        payload = tomlkit.dumps(doc)
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w",
                dir=str(parent_dir),
                delete=False,
                encoding="utf-8",
                prefix="settings_",
                suffix=".tmp",
            )
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()

            os.replace(temp_file.name, str(self._path))
        except Exception as ex:
            _logger.error("Failed to atomically save configuration to TOML at %s: %s", self._path, ex)
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.remove(temp_file.name)
                except OSError:
                    pass
            raise


class LocalJsonConfigStore:
    """
    Thread-safe JSON file configuration adapter with atomic write-and-replace semantics.
    """

    def __init__(self, file_path: Optional[Union[str, Path]] = None):
        if file_path is None:
            caster_user_dir = Path.home() / ".caster"
            self._path = caster_user_dir / "plugin_configs.json"
        else:
            self._path = Path(file_path).resolve()

        self._lock = threading.RLock()
        self._cached_configs: Dict[str, Dict[str, Any]] = {}
        self._is_loaded = False

    @property
    def path(self) -> Path:
        return self._path

    def _ensure_loaded(self):
        if self._is_loaded:
            return

        if not self._path.exists():
            self._cached_configs = {}
            self._is_loaded = True
            return

        try:
            content = self._path.read_text(encoding="utf-8").strip()
            if not content:
                self._cached_configs = {}
            else:
                data = json.loads(content)
                if isinstance(data, dict):
                    self._cached_configs = {
                        str(k): dict(v) for k, v in data.items() if isinstance(v, dict)
                    }
                else:
                    self._cached_configs = {}
        except Exception as ex:
            _logger.warning("Failed to parse plugin config store from %s: %s", self._path, ex)
            self._cached_configs = {}

        self._is_loaded = True

    def get_plugin_config(
        self, plugin_name: str, definitions: Dict[str, OptionDefinition]
    ) -> Dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            overrides = self._cached_configs.get(plugin_name, {})
            effective: Dict[str, Any] = {}

            for opt_name, defn in definitions.items():
                if opt_name in overrides:
                    raw_val = overrides[opt_name]
                    is_valid, coerced_val, _ = validate_and_coerce(defn, raw_val)
                    if is_valid:
                        effective[opt_name] = coerced_val
                    else:
                        effective[opt_name] = defn.default
                else:
                    effective[opt_name] = defn.default

            return effective

    def set_plugin_config(
        self,
        plugin_name: str,
        config: Dict[str, Any],
        definitions: Dict[str, OptionDefinition],
    ) -> Dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            valid_overrides: Dict[str, Any] = {}
            for key, val in config.items():
                if key in definitions:
                    defn = definitions[key]
                    is_valid, coerced_val, err_msg = validate_and_coerce(defn, val)
                    if not is_valid:
                        raise ValueError(f"Invalid value for option '{key}': {err_msg}")
                    valid_overrides[key] = coerced_val

            self._cached_configs[plugin_name] = valid_overrides
            self._flush_to_disk()
            return self.get_plugin_config(plugin_name, definitions)

    def reset_plugin_config(
        self, plugin_name: str, definitions: Dict[str, OptionDefinition]
    ) -> Dict[str, Any]:
        with self._lock:
            self._ensure_loaded()
            if plugin_name in self._cached_configs:
                del self._cached_configs[plugin_name]
                self._flush_to_disk()
            return self.get_plugin_config(plugin_name, definitions)

    def _flush_to_disk(self):
        parent_dir = self._path.parent
        parent_dir.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self._cached_configs, indent=2, sort_keys=True)
        temp_file = None
        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w",
                dir=str(parent_dir),
                delete=False,
                encoding="utf-8",
                prefix="plugin_configs_",
                suffix=".tmp",
            )
            temp_file.write(payload)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()

            os.replace(temp_file.name, str(self._path))
        except Exception as ex:
            _logger.error("Failed to atomically save plugin configs to %s: %s", self._path, ex)
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.remove(temp_file.name)
                except OSError:
                    pass
            raise


def PluginConfigStore(file_path: Optional[Union[str, Path]] = None):  # noqa: N802
    """
    Factory creating a configuration store. Selects LocalJsonConfigStore if a .json path
    is provided; otherwise returns CasterTomlConfigStore targeting settings.toml.
    """
    if file_path is not None and str(file_path).endswith(".json"):
        return LocalJsonConfigStore(file_path=file_path)
    return CasterTomlConfigStore(file_path=file_path)
