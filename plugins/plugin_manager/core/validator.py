# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Environment, platform, and dependency validator for Caster plugins.
Uses standard library importlib.metadata and platform checks.
"""

import importlib.metadata
import importlib.util
import logging
import sys
from typing import List, Optional, Tuple

from .models import PluginHealthState, PluginMetadata, PluginRecord

_logger = logging.getLogger("caster.plugins.plugin_manager.validator")


def get_current_platform() -> str:
    """Returns normalized platform identifier ('windows', 'linux', 'darwin')."""
    plat = sys.platform.lower()
    if plat.startswith("win"):
        return "windows"
    if plat.startswith("linux"):
        return "linux"
    if plat.startswith("darwin"):
        return "darwin"
    return plat


class PluginValidator:
    """
    Evaluates platform compatibility and dependency satisfaction without executing plugin code.
    """

    def __init__(self, target_platform: Optional[str] = None):
        self._target_platform = target_platform or get_current_platform()

    def is_platform_supported(self, metadata: PluginMetadata) -> bool:
        """Checks if current platform satisfies declared platforms in metadata."""
        if not metadata.platforms:
            return True

        normalized_declared = []
        for p in metadata.platforms:
            p_clean = p.strip().lower()
            if p_clean in ("win32", "windows"):
                normalized_declared.append("windows")
            elif p_clean in ("linux", "linux2"):
                normalized_declared.append("linux")
            elif p_clean in ("darwin", "macos", "osx"):
                normalized_declared.append("darwin")
            else:
                normalized_declared.append(p_clean)

        return self._target_platform in normalized_declared

    def check_dependency(self, dep_name: str) -> bool:
        """
        Checks if a Python package dependency is installed.
        Inspects distribution metadata first, then falls back to module spec lookup.
        """
        clean_name = dep_name.strip()
        if not clean_name:
            return True

        # Extract base package name if version constraint present (e.g. "PySide2>=5.15")
        for op in (">=", "<=", "==", "!=", "~=", ">", "<"):
            if op in clean_name:
                clean_name = clean_name.split(op)[0].strip()
                break

        # 1. Check via importlib.metadata distribution
        try:
            importlib.metadata.distribution(clean_name)
            return True
        except (importlib.metadata.PackageNotFoundError, ValueError):
            pass

        # 2. Check via module spec resolution
        try:
            spec = importlib.util.find_spec(clean_name)
            if spec is not None:
                return True
        except (ModuleNotFoundError, ValueError, AttributeError):
            pass

        return False

    def validate_dependencies(self, metadata: PluginMetadata) -> Tuple[bool, List[str]]:
        """Returns boolean success flag and list of missing dependency package names."""
        missing: List[str] = []
        for dep in metadata.dependencies:
            if not self.check_dependency(dep):
                missing.append(dep)
        return len(missing) == 0, missing

    def validate_record(self, record: PluginRecord) -> PluginRecord:
        """
        Performs full environment and dependency validation on a PluginRecord
        and updates its health state accordingly.
        """
        if record.health == PluginHealthState.MALFORMED_METADATA:
            return record

        # 1. Check platform
        if not self.is_platform_supported(record.metadata):
            record.health = PluginHealthState.INCOMPATIBLE_PLATFORM
            record.diagnostic_message = "Incompatible platform: current '{}' not in {}".format(
                self._target_platform, record.metadata.platforms
            )
            return record

        # 2. Check dependencies
        deps_satisfied, missing = self.validate_dependencies(record.metadata)
        record.missing_dependencies = missing
        if not deps_satisfied:
            record.health = PluginHealthState.MISSING_DEPENDENCIES
            record.diagnostic_message = "Missing required dependencies: {}".format(", ".join(missing))
            return record

        # 3. Reflect enabled/disabled state
        if not record.enabled:
            record.health = PluginHealthState.DISABLED
            record.diagnostic_message = None
        else:
            record.health = PluginHealthState.READY
            record.diagnostic_message = None

        return record
