"""
Abstract Context Provider Interface for Pluggable Desktop Engines.
"""

from abc import ABC, abstractmethod
from typing import Optional

from hud.core.state import DesktopContextState


class IContextProvider(ABC):
    """
    Interface for external context engines (e.g. Active Desktop Context Engine / ADCE).
    Allows external daemons to donate semantic focus zones without creating hard dependencies.
    """

    @abstractmethod
    def is_connected(self) -> bool:
        """Returns True if the underlying context engine is online and streaming."""
        pass

    @abstractmethod
    def get_current_context(self) -> DesktopContextState:
        """Returns the latest in-memory desktop context snapshot."""
        pass


class NullContextProvider(IContextProvider):
    """Default fallback context provider when no external context engine is active."""

    def is_connected(self) -> bool:
        return False

    def get_current_context(self) -> DesktopContextState:
        return DesktopContextState()
