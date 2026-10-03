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

from .options import OptionDefinition, validate_and_coerce

_logger = logging.getLogger("caster.plugins.plugin_manager.config_store")


class PluginConfigStore:
    """
    Manages loading, merging, validating, and saving per-plugin configuration parameters.
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
        """Loads configuration from disk if not already loaded into cache."""
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
        """
        Returns effective configuration dictionary for a plugin, merging stored overrides
        over schema defaults.
        """
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
        """
        Validates, applies, and atomically flushes configuration overrides for a plugin.
        Raises ValueError if any configuration value fails validation.
        """
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
        """
        Removes saved user overrides for a plugin, reverting all options to schema defaults.
        """
        with self._lock:
            self._ensure_loaded()
            if plugin_name in self._cached_configs:
                del self._cached_configs[plugin_name]
                self._flush_to_disk()
            return self.get_plugin_config(plugin_name, definitions)

    def _flush_to_disk(self):
        """Atomically saves all cached configurations to disk."""
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
