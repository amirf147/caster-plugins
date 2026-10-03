# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Detail inspector pane displaying full plugin metadata and diagnostics.
"""

import os
import subprocess
import sys
from typing import Optional

try:
    from PySide2 import QtCore, QtWidgets
except ImportError:
    try:
        from PyQt5 import QtCore, QtWidgets
    except ImportError:
        from castervoice.lib.qt import QtCore, QtWidgets

from ...core.models import PluginRecord
from ..theme import (
    COLOR_BORDER,
    COLOR_HEALTH_ERROR,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
)


class DetailPane(QtWidgets.QFrame):
    """
    Inspector pane presenting complete metadata, diagnostic alerts, and directory actions.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setObjectName("detailFrame")
        self._current_record: Optional[PluginRecord] = None
        self._init_ui()
        self.clear()

    def _init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title and Version
        self._title_label = QtWidgets.QLabel(self)
        self._title_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {COLOR_TEXT_PRIMARY};")
        layout.addWidget(self._title_label)

        # Author / Version Subhead
        self._meta_subhead = QtWidgets.QLabel(self)
        self._meta_subhead.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 12px;")
        layout.addWidget(self._meta_subhead)

        # Divider
        divider = QtWidgets.QFrame(self)
        divider.setFrameShape(QtWidgets.QFrame.HLine)
        divider.setStyleSheet(f"color: {COLOR_BORDER}; background-color: {COLOR_BORDER}; max-height: 1px;")
        layout.addWidget(divider)

        # Description
        self._desc_label = QtWidgets.QLabel(self)
        self._desc_label.setWordWrap(True)
        self._desc_label.setStyleSheet(f"color: {COLOR_TEXT_PRIMARY}; line-height: 140%;")
        layout.addWidget(self._desc_label)

        # Metadata Details Form
        form_layout = QtWidgets.QFormLayout()
        form_layout.setSpacing(6)
        form_layout.setLabelAlignment(QtCore.Qt.AlignLeft)

        self._platforms_val = QtWidgets.QLabel(self)
        self._platforms_val.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        form_layout.addRow("<b>Platforms:</b>", self._platforms_val)

        self._deps_val = QtWidgets.QLabel(self)
        self._deps_val.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        form_layout.addRow("<b>Dependencies:</b>", self._deps_val)

        self._entry_val = QtWidgets.QLabel(self)
        self._entry_val.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        form_layout.addRow("<b>Entry Point:</b>", self._entry_val)

        self._path_val = QtWidgets.QLabel(self)
        self._path_val.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-size: 11px;")
        self._path_val.setWordWrap(True)
        form_layout.addRow("<b>Path:</b>", self._path_val)

        layout.addLayout(form_layout)

        # Diagnostic Alert Box
        self._diag_frame = QtWidgets.QFrame(self)
        self._diag_frame.setObjectName("diagnosticAlert")
        diag_layout = QtWidgets.QVBoxLayout(self._diag_frame)
        diag_layout.setContentsMargins(8, 8, 8, 8)
        diag_layout.setSpacing(4)

        diag_title = QtWidgets.QLabel("<b>Diagnostic Issue:</b>", self._diag_frame)
        diag_title.setStyleSheet(f"color: {COLOR_HEALTH_ERROR}; font-size: 12px;")
        diag_layout.addWidget(diag_title)

        self._diag_text = QtWidgets.QLabel(self._diag_frame)
        self._diag_text.setWordWrap(True)
        self._diag_text.setStyleSheet("color: #ffb4a2; font-size: 11px;")
        diag_layout.addWidget(self._diag_text)

        layout.addWidget(self._diag_frame)
        self._diag_frame.hide()

        layout.addStretch()

        # Action Buttons
        actions_layout = QtWidgets.QHBoxLayout()
        self._open_dir_btn = QtWidgets.QPushButton("Open Folder", self)
        self._open_dir_btn.clicked.connect(self._on_open_folder_clicked)
        actions_layout.addWidget(self._open_dir_btn)
        actions_layout.addStretch()

        layout.addLayout(actions_layout)

    def set_plugin(self, record: Optional[PluginRecord]):
        """Populates detail pane with information from specified record."""
        self._current_record = record
        if record is None:
            self.clear()
            return

        meta = record.metadata
        self._title_label.setText(meta.name)
        author_text = f"by {meta.author}" if meta.author else "Unknown author"
        self._meta_subhead.setText(f"Version {meta.version} • {author_text}")
        self._desc_label.setText(meta.description or "No description provided.")

        platforms_text = ", ".join(meta.platforms) if meta.platforms else "All platforms"
        self._platforms_val.setText(platforms_text)

        deps_text = ", ".join(meta.dependencies) if meta.dependencies else "None"
        self._deps_val.setText(deps_text)

        self._entry_val.setText(meta.entry_point or "None")
        self._path_val.setText(str(meta.plugin_dir) if meta.plugin_dir else "N/A")

        if record.diagnostic_message:
            self._diag_text.setText(record.diagnostic_message)
            self._diag_frame.show()
        else:
            self._diag_frame.hide()

        self._open_dir_btn.setEnabled(bool(meta.plugin_dir and meta.plugin_dir.exists()))

    def clear(self):
        """Resets inspector to empty placeholder state."""
        self._current_record = None
        self._title_label.setText("Select a plugin")
        self._meta_subhead.setText("")
        self._desc_label.setText("Select a plugin from the list on the left to inspect metadata, requirements, and diagnostics.")
        self._platforms_val.setText("-")
        self._deps_val.setText("-")
        self._entry_val.setText("-")
        self._path_val.setText("-")
        self._diag_frame.hide()
        self._open_dir_btn.setEnabled(False)

    def _on_open_folder_clicked(self):
        if not self._current_record or not self._current_record.metadata.plugin_dir:
            return

        path = str(self._current_record.metadata.plugin_dir)
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform.startswith("darwin"):
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
