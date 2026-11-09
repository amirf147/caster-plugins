# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Core headless registry engine, models, scanner, validator, and storage adapters.
"""

from .config_store import CasterTomlConfigStore, PluginConfigStore
from .models import PluginHealthState, PluginMetadata, PluginRecord
from .options import OptionDefinition, OptionType, validate_and_coerce
from .registry import PluginRegistry
from .scanner import PluginScanner
from .storage import (
    CasterTomlStateAdapter,
    LocalJsonStateAdapter,
    SettingsTomlStore,
    StateStorageAdapter,
)
from .validator import PluginValidator

__all__ = [
    "CasterTomlConfigStore",
    "CasterTomlStateAdapter",
    "LocalJsonStateAdapter",
    "OptionDefinition",
    "OptionType",
    "PluginConfigStore",
    "PluginHealthState",
    "PluginMetadata",
    "PluginRecord",
    "PluginRegistry",
    "PluginScanner",
    "PluginValidator",
    "SettingsTomlStore",
    "StateStorageAdapter",
    "validate_and_coerce",
]
