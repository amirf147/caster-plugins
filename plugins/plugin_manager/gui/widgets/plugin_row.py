# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
List item row widget representing a single plugin with status badge and toggle switch.
"""

from typing import Optional

try:
    from PySide2 import QtCore, QtWidgets
    from PySide2.QtCore import Signal
except ImportError:
    try:
        from PyQt5 import QtCore, QtWidgets
        from PyQt5.QtCore import pyqtSignal as Signal
    except ImportError:
        from castervoice.lib.qt import QtCore, QtWidgets

        Signal = getattr(QtCore, "Signal", getattr(QtCore, "pyqtSignal", None))

from ...core.models import PluginHealthState, PluginRecord
from ..theme import (
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
    get_health_color,
)


class PluginRowWidget(QtWidgets.QWidget):
    """
    Renders an individual plugin card within QListWidget with health badge and toggle button.
    """

    # Signal emitted when user clicks toggle: (plugin_name, new_enabled_state)
    toggled = Signal(str, bool)

    def __init__(self, record: PluginRecord, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._record = record
        self._init_ui()
        self.update_record(record)

    @property
    def record(self) -> PluginRecord:
        return self._record

    def _init_ui(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(12)

        # Health status badge
        self._badge = QtWidgets.QLabel(self)
        self._badge.setMinimumWidth(85)
        self._badge.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self._badge)

        # Text column (Name, version, short description)
        text_layout = QtWidgets.QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(8)

        self._name_label = QtWidgets.QLabel(self)
        self._name_label.setStyleSheet(f"font-weight: 700; font-size: 14px; color: {COLOR_TEXT_PRIMARY};")
        header_layout.addWidget(self._name_label)

        self._version_label = QtWidgets.QLabel(self)
        self._version_label.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
        header_layout.addWidget(self._version_label)
        header_layout.addStretch()

        text_layout.addLayout(header_layout)

        self._desc_label = QtWidgets.QLabel(self)
        self._desc_label.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px;")
        text_layout.addWidget(self._desc_label)

        layout.addLayout(text_layout, stretch=1)

        # Toggle Button
        self._toggle_btn = QtWidgets.QPushButton(self)
        self._toggle_btn.setMinimumWidth(90)
        self._toggle_btn.clicked.connect(self._on_toggle_clicked)
        layout.addWidget(self._toggle_btn)

    def update_record(self, record: PluginRecord):
        """Updates widget fields from a new or mutated PluginRecord."""
        self._record = record
        meta = record.metadata

        self._name_label.setText(meta.name)
        self._version_label.setText(f"v{meta.version}")
        self._desc_label.setText(meta.description or "No description provided.")

        # Format health badge
        color = get_health_color(record.health.value)
        health_text = record.health.value.replace("_", " ").upper()
        self._badge.setText(f" {health_text} ")
        self._badge.setStyleSheet(
            f"background-color: {color}; color: #ffffff; border-radius: 4px; "
            f"padding: 3px 6px; font-size: 10px; font-weight: bold;"
        )

        # Configure toggle button based on health and enabled status
        is_operable = record.health in (PluginHealthState.READY, PluginHealthState.DISABLED)
        if not is_operable:
            self._toggle_btn.setText("Unavailable")
            self._toggle_btn.setEnabled(False)
            self._toggle_btn.setStyleSheet("")
        elif record.enabled:
            self._toggle_btn.setText("Enabled")
            self._toggle_btn.setEnabled(True)
            self._toggle_btn.setObjectName("primaryButton")
            self._toggle_btn.setStyleSheet("")
        else:
            self._toggle_btn.setText("Disabled")
            self._toggle_btn.setEnabled(True)
            self._toggle_btn.setObjectName("")
            self._toggle_btn.setStyleSheet("")

        # Re-apply styles after object name changes
        self._toggle_btn.style().unpolish(self._toggle_btn)
        self._toggle_btn.style().polish(self._toggle_btn)

    def _on_toggle_clicked(self):
        new_state = not self._record.enabled
        self.toggled.emit(self._record.metadata.name, new_state)
