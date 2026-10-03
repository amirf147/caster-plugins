# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Thread-safe, atomic persistence storage adapters for plugin states.
"""

import abc
import json
import logging
import os
from pathlib import Path
import tempfile
import threading
from typing import Dict, Optional, Union

import tomlkit

_logger = logging.getLogger("caster.plugins.plugin_manager.storage")


def resolve_caster_settings_path(file_path: Optional[Union[str, Path]] = None) -> Path:
    """
    Resolves the authoritative path to Caster's settings.toml file across execution environments.
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


class CasterTomlStateAdapter(StateStorageAdapter):
    """
    Format-preserving TOML state storage adapter operating directly on Caster's settings.toml.
    """

    def __init__(self, file_path: Optional[Union[str, Path]] = None):
        self._path = resolve_caster_settings_path(file_path)
        self._lock = threading.RLock()

    @property
    def path(self) -> Path:
        return self._path

    def load_state(self) -> Dict[str, bool]:
        """Loads plugin activation state dictionary from settings.toml with thread synchronization."""
        with self._lock:
            if not self._path.exists():
                return {}

            try:
                content = self._path.read_text(encoding="utf-8")
                if not content.strip():
                    return {}

                doc = tomlkit.parse(content)
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
            except Exception as ex:
                _logger.warning("Failed to parse plugin states from TOML at %s: %s", self._path, ex)
                return {}

    def save_state(self, state: Dict[str, bool]) -> None:
        """
        Atomically updates the [plugins] table in settings.toml preserving comments and structure.
        """
        with self._lock:
            parent_dir = self._path.parent
            parent_dir.mkdir(parents=True, exist_ok=True)

            doc = tomlkit.document()
            if self._path.exists():
                try:
                    content = self._path.read_text(encoding="utf-8")
                    if content.strip():
                        doc = tomlkit.parse(content)
                except Exception as ex:
                    _logger.warning("Failed to parse existing TOML at %s, starting fresh: %s", self._path, ex)

            if "plugins" not in doc or not isinstance(doc["plugins"], dict):
                doc["plugins"] = tomlkit.table()

            plugins_table = doc["plugins"]
            for name, enabled in state.items():
                if name in plugins_table and (isinstance(plugins_table[name], dict) or hasattr(plugins_table[name], "get")):
                    plugins_table[name]["enabled"] = bool(enabled)
                else:
                    plugins_table[name] = bool(enabled)

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
                _logger.error("Failed to atomically save plugin states to TOML at %s: %s", self._path, ex)
                if temp_file and os.path.exists(temp_file.name):
                    try:
                        os.remove(temp_file.name)
                    except OSError:
                        pass
                raise


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
        Atomically writes state to a temporary file in the target directory,
        then replaces the target file.
        """
        with self._lock:
            parent_dir = self._path.parent
            parent_dir.mkdir(parents=True, exist_ok=True)

            # Convert state map to serializable dict
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

                # Atomic replacement on POSIX and Windows (Python 3.3+)
                os.replace(temp_file.name, str(self._path))
            except Exception as ex:
                _logger.error("Failed to atomically save plugin states to %s: %s", self._path, ex)
                if temp_file and os.path.exists(temp_file.name):
                    try:
                        os.remove(temp_file.name)
                    except OSError:
                        pass
                raise
