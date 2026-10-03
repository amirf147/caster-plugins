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

_logger = logging.getLogger("caster.plugins.plugin_manager.storage")


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
