# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Core headless registry engine, models, scanner, validator, and storage adapters.
"""

from .config_store import PluginConfigStore
from .models import PluginHealthState, PluginMetadata, PluginRecord
from .options import OptionDefinition, OptionType, validate_and_coerce
from .registry import PluginRegistry
from .scanner import PluginScanner
from .storage import LocalJsonStateAdapter, StateStorageAdapter
from .validator import PluginValidator

__all__ = [
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
    "StateStorageAdapter",
    "validate_and_coerce",
]
