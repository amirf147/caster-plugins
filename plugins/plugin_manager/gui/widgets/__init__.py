# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Custom presentation widgets for Caster Plugin Manager.
"""

from .detail_pane import DetailPane
from .plugin_row import PluginRowWidget
from .settings_form import SettingsFormWidget

__all__ = [
    "DetailPane",
    "PluginRowWidget",
    "SettingsFormWidget",
]
