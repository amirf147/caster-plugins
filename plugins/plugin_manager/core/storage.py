# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Thread-safe, atomic persistence storage adapters for plugin states and settings.
"""

import abc
import json
import logging
import os
from pathlib import Path
import tempfile
import threading
from typing import Any, Dict, Optional, Union

import tomlkit

from .options import OptionDefinition, validate_and_coerce

_logger = logging.getLogger("caster.plugins.plugin_manager.storage")


def resolve_caster_settings_path(file_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolves authoritative path to Caster settings.toml across execution environments.
    """
    if file_path is not None:
        return Path(file_path).resolve()

    try:
        from castervoice.lib import settings
        fn = settings.get_filename()
        if fn:
            return Path(fn).resolve()
    except Exception:
        pass

    user_dir_env = os.environ.get("CASTER_USER_DIR")
    if user_dir_env:
        return Path(user_dir_env).resolve() / "settings" / "settings.toml"

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return (Path(local_app_data) / "caster" / "settings" / "settings.toml").resolve()

    return (Path.home() / ".caster" / "settings" / "settings.toml").resolve()


class StateStorageAdapter(abc.ABC):
    """Abstract interface defining the contract for plugin state persistence."""

    @abc.abstractmethod
    def load_state(self) -> Dict[str, bool]:
        """Loads and returns mapping of plugin names to enabled booleans."""
        pass

    @abc.abstractmethod
    def save_state(self, state: Dict[str, bool]) -> None:
        """Atomically persists plugin enabled state mapping."""
        pass


class SettingsTomlStore(StateStorageAdapter):
    """
    Unified thread-safe, atomic persistence store for Caster settings.toml.
    Manages both plugin activation states and configuration options.
    Instances targeting the same filesystem path share a single threading.RLock.
    """

    _locks: Dict[Path, threading.RLock] = {}
    _registry_lock = threading.Lock()

    @classmethod
    def _get_lock_for_path(cls, path: Path) -> threading.RLock:
        resolved = path.resolve()
        with cls._registry_lock:
            if resolved not in cls._locks:
                cls._locks[resolved] = threading.RLock()
            return cls._locks[resolved]

    def __init__(self, file_path: Optional[Union[str, Path]] = None):
        self._path = resolve_caster_settings_path(file_path)
        self._lock = self._get_lock_for_path(self._path)

    @property
    def path(self) -> Path:
        return self._path

    @property
    def lock(self) -> threading.RLock:
        return self._lock

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
            _logger.error("Failed to atomically save TOML to %s: %s", self._path, ex)
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.remove(temp_file.name)
                except OSError:
                    pass
            raise

    def load_state(self) -> Dict[str, bool]:
        """Loads plugin activation state dictionary from settings.toml with thread synchronization."""
        with self._lock:
            doc = self._read_doc()
            plugins = doc.get("plugins")
            if not plugins or not isinstance(plugins, dict):
                return {}

            state: Dict[str, bool] = {}
            for name, val in plugins.items():
                if isinstance(val, bool):
                    state[name] = val
                elif isinstance(val, dict) or hasattr(val, "get"):
                    state[name] = bool(val.get("enabled", False))
                else:
                    state[name] = bool(val)
            return state

    def save_state(self, state: Dict[str, bool]) -> None:
        """
        Atomically updates the [plugins] table in settings.toml preserving comments,
        table structure, and plugin options.
        """
        with self._lock:
            doc = self._read_doc()
            if "plugins" not in doc or not isinstance(doc["plugins"], dict):
                doc["plugins"] = tomlkit.table()

            plugins_table = doc["plugins"]
            for name, enabled in state.items():
                if name in plugins_table:
                    val = plugins_table[name]
                    if isinstance(val, dict) or hasattr(val, "get"):
                        val["enabled"] = bool(enabled)
                    else:
                        plugins_table[name] = bool(enabled)
                else:
                    plugins_table[name] = bool(enabled)

            self._atomic_write(doc)

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
            valid_overrides: Dict[str, Any] = {}
            for key, val in config.items():
                if key in definitions:
                    defn = definitions[key]
                    is_valid, coerced_val, err_msg = validate_and_coerce(defn, val)
                    if not is_valid:
                        raise ValueError(f"Invalid value for option '{key}': {err_msg}")
                    valid_overrides[key] = coerced_val

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
        Removes saved option overrides for a plugin in settings.toml, reverting all options to schema defaults
        while preserving plugin activation state.
        """
        with self._lock:
            doc = self._read_doc()
            plugins = doc.get("plugins")
            if isinstance(plugins, dict) and plugin_name in plugins:
                existing = plugins[plugin_name]
                if isinstance(existing, dict) or hasattr(existing, "get"):
                    for opt_name in definitions.keys():
                        if opt_name in existing:
                            del existing[opt_name]
                    self._atomic_write(doc)

            return self.get_plugin_config(plugin_name, definitions)


class CasterTomlStateAdapter(SettingsTomlStore):
    """
    Format-preserving TOML state storage adapter operating directly on Caster settings.toml.
    Subclasses unified SettingsTomlStore.
    """
    pass


class LocalJsonStateAdapter(StateStorageAdapter):
    """
    Thread-safe JSON file storage adapter with atomic write-and-replace semantics.
    """

    def __init__(self, file_path: Optional[Union[str, Path]] = None):
        if file_path is None:
            caster_user_dir = Path.home() / ".caster"
            self._path = caster_user_dir / "plugin_states.json"
        else:
            self._path = Path(file_path).resolve()

        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    def load_state(self) -> Dict[str, bool]:
        """Loads state dictionary from JSON file with thread-lock synchronization."""
        with self._lock:
            if not self._path.exists():
                return {}

            try:
                content = self._path.read_text(encoding="utf-8").strip()
                if not content:
                    return {}
                data = json.loads(content)
                if isinstance(data, dict):
                    return {str(k): bool(v) for k, v in data.items()}
                return {}
            except Exception as ex:
                _logger.warning("Failed to parse plugin state store from %s: %s", self._path, ex)
                return {}

    def save_state(self, state: Dict[str, bool]) -> None:
        """
        Atomically writes state to temporary file in target directory,
        then replaces target file.
        """
        with self._lock:
            parent_dir = self._path.parent
            parent_dir.mkdir(parents=True, exist_ok=True)

            clean_state = {str(k): bool(v) for k, v in state.items()}
            payload = json.dumps(clean_state, indent=2, sort_keys=True)

            temp_file = None
            try:
                temp_file = tempfile.NamedTemporaryFile(
                    mode="w",
                    dir=str(parent_dir),
                    delete=False,
                    encoding="utf-8",
                    prefix="plugin_states_",
                    suffix=".tmp",
                )
                temp_file.write(payload)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_file.close()

                os.replace(temp_file.name, str(self._path))
            except Exception as ex:
                _logger.error("Failed to atomically save plugin states to %s: %s", self._path, ex)
                if temp_file and os.path.exists(temp_file.name):
                    try:
                        os.remove(temp_file.name)
                    except OSError:
                        pass
                raise
