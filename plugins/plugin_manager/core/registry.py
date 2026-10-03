# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Headless PluginRegistry controller uniting scanner, validator, and storage.
"""

from pathlib import Path
import threading
from typing import Any, Dict, List, Optional, Union

from .config_store import PluginConfigStore
from .models import PluginRecord
from .scanner import PluginScanner
from .storage import LocalJsonStateAdapter, StateStorageAdapter
from .validator import PluginValidator


class PluginRegistry:
    """
    Central controller managing discovery, validation, and persistent state for plugins.
    Completely decoupled from any presentation framework.
    """

    def __init__(
        self,
        search_dirs: Optional[List[Union[str, Path]]] = None,
        storage: Optional[StateStorageAdapter] = None,
        config_store: Optional[PluginConfigStore] = None,
        validator: Optional[PluginValidator] = None,
        manifest_path: Optional[Union[str, Path]] = None,
    ):
        self._scanner = PluginScanner(search_dirs=search_dirs, manifest_path=manifest_path)
        self._storage = storage or LocalJsonStateAdapter()
        self._config_store = config_store or PluginConfigStore()
        self._validator = validator or PluginValidator()
        self._cache: Dict[str, PluginRecord] = {}
        self._lock = threading.RLock()

    @property
    def storage(self) -> StateStorageAdapter:
        return self._storage

    @property
    def config_store(self) -> PluginConfigStore:
        return self._config_store

    @property
    def validator(self) -> PluginValidator:
        return self._validator

    @property
    def scanner(self) -> PluginScanner:
        return self._scanner

    def scan(self) -> Dict[str, PluginRecord]:
        """
        Discovers all plugins from search directories, applies persisted enabled state,
        evaluates environment health, and caches results.
        """
        with self._lock:
            discovered = self._scanner.scan_all()
            saved_state = self._storage.load_state()

            self._cache.clear()
            for name, record in discovered.items():
                record.enabled = saved_state.get(name, False)
                self._validator.validate_record(record)
                self._cache[name] = record

            return dict(self._cache)

    def get_plugins(self) -> Dict[str, PluginRecord]:
        """
        Returns all registered plugin records. Populates cache if not yet scanned.
        """
        with self._lock:
            if not self._cache:
                self.scan()
            return dict(self._cache)

    def get_plugin(self, name: str) -> Optional[PluginRecord]:
        """
        Retrieves a single plugin record by unique name.
        """
        with self._lock:
            if not self._cache:
                self.scan()
            return self._cache.get(name)

    def set_enabled(self, name: str, enabled: bool) -> PluginRecord:
        """
        Mutates user intent for a plugin, re-validates health state,
        and atomically flushes changes to storage.
        """
        with self._lock:
            if not self._cache:
                self.scan()

            record = self._cache.get(name)
            if record is None:
                raise KeyError("Plugin '{}' is not registered in search paths".format(name))

            record.enabled = bool(enabled)
            self._validator.validate_record(record)

            # Persist updated enabled map
            state_map = {p_name: p_rec.enabled for p_name, p_rec in self._cache.items()}
            self._storage.save_state(state_map)

            return record

    def get_plugin_config(self, name: str) -> Dict[str, Any]:
        """
        Returns effective configuration dictionary for a specified plugin.
        """
        with self._lock:
            record = self.get_plugin(name)
            if record is None:
                raise KeyError("Plugin '{}' is not registered in search paths".format(name))
            return self._config_store.get_plugin_config(name, record.metadata.options)

    def set_plugin_config(self, name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates, applies, and persists configuration dictionary for a specified plugin.
        """
        with self._lock:
            record = self.get_plugin(name)
            if record is None:
                raise KeyError("Plugin '{}' is not registered in search paths".format(name))
            return self._config_store.set_plugin_config(name, config, record.metadata.options)

    def reset_plugin_config(self, name: str) -> Dict[str, Any]:
        """
        Resets a plugin's configuration back to schema defaults.
        """
        with self._lock:
            record = self.get_plugin(name)
            if record is None:
                raise KeyError("Plugin '{}' is not registered in search paths".format(name))
            return self._config_store.reset_plugin_config(name, record.metadata.options)

    def validate(self, name: str) -> PluginRecord:
        """
        Forces re-validation of environment and dependencies for a specific plugin.
        """
        with self._lock:
            if not self._cache:
                self.scan()

            record = self._cache.get(name)
            if record is None:
                raise KeyError("Plugin '{}' is not registered in search paths".format(name))

            self._validator.validate_record(record)
            return record

    def export_records(self) -> List[Dict[str, Any]]:
        """
        Exports list of serialized dictionary records sorted by name.
        """
        with self._lock:
            plugins = self.get_plugins()
            return [plugins[name].to_dict() for name in sorted(plugins.keys())]
