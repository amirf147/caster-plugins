# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Data models and state representations for Caster Plugin Manager.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .options import OptionDefinition


class PluginHealthState(str, Enum):
    """
    Finite state machine representing the operational and environment health
    of a discovered plugin.
    """
    READY = "ready"
    DISABLED = "disabled"
    MISSING_DEPENDENCIES = "missing_dependencies"
    INCOMPATIBLE_PLATFORM = "incompatible_platform"
    MALFORMED_METADATA = "malformed_metadata"
    LOAD_ERROR = "load_error"


@dataclass(frozen=True)
class PluginMetadata:
    """
    Immutable representation of plugin metadata declared in metadata.toml or manifest.json.
    """
    name: str
    version: str
    description: str
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    min_caster_version: Optional[str] = None
    platforms: List[str] = field(default_factory=lambda: ["windows", "linux", "darwin"])
    entry_point: Optional[str] = None
    plugin_dir: Optional[Path] = None
    options: Dict[str, OptionDefinition] = field(default_factory=dict)


@dataclass
class PluginRecord:
    """
    Mutable runtime state record joining immutable metadata, user intent,
    and resolved health/environment validation.
    """
    metadata: PluginMetadata
    enabled: bool = False
    health: PluginHealthState = PluginHealthState.READY
    missing_dependencies: List[str] = field(default_factory=list)
    diagnostic_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes record to a plain dictionary for UI presentation or IPC transmission."""
        return {
            "name": self.metadata.name,
            "version": self.metadata.version,
            "description": self.metadata.description,
            "author": self.metadata.author,
            "dependencies": list(self.metadata.dependencies),
            "min_caster_version": self.metadata.min_caster_version,
            "platforms": list(self.metadata.platforms),
            "entry_point": self.metadata.entry_point,
            "plugin_dir": str(self.metadata.plugin_dir) if self.metadata.plugin_dir else None,
            "options": {k: opt.to_dict() for k, opt in self.metadata.options.items()},
            "enabled": self.enabled,
            "health": self.health.value,
            "missing_dependencies": list(self.missing_dependencies),
            "diagnostic_message": self.diagnostic_message,
        }
