# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Fallback PluginBase interface for environments where Caster core plugin framework
is not yet installed in site-packages or upstream dependencies.
"""


class PluginBase(object):
    """
    Abstract base class establishing the lifecycle contract for Caster plugins.
    """

    name = "base_plugin"
    version = "0.1.0"
    description = "Base Caster Plugin"
    aliases = []

    def __init__(self):
        self._nexus = None
        self._config = {}
        self._is_running = False

    @property
    def is_running(self):
        return self._is_running

    def initialize(self, nexus, config):
        """
        Called during Caster startup prior to speech engine initialization.
        """
        self._nexus = nexus
        self._config = config or {}

    def start(self):
        """
        Called after engine configuration has completed.
        """
        self._is_running = True

    def stop(self):
        """
        Called during Caster shutdown or reload.
        """
        self._is_running = False

    def get_rules(self):
        """
        Returns a list of Dragonfly Rule classes or (RuleClass, RuleDetails) tuples.
        """
        return []
