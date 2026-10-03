# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Main top-level pop-up dialog for Caster Plugin Manager.
"""

from typing import Dict, Optional

try:
    from PySide2 import QtCore, QtGui, QtWidgets
except ImportError:
    try:
        from PyQt5 import QtCore, QtGui, QtWidgets
    except ImportError:
        from castervoice.lib.qt import QtCore, QtGui, QtWidgets

from ..core.models import PluginHealthState, PluginRecord
from ..core.registry import PluginRegistry
from .theme import get_stylesheet
from .widgets.detail_pane import DetailPane
from .widgets.plugin_row import PluginRowWidget
from .widgets.settings_form import SettingsFormWidget


class PluginManagerWindow(QtWidgets.QDialog):
    """
    Top-level dialog displaying installed plugins, health metrics, and configuration toggles.
    """

    _DEFAULT_WIDTH = 780
    _DEFAULT_HEIGHT = 520

    def __init__(self, registry: Optional[PluginRegistry] = None, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._registry = registry or PluginRegistry()
        self._row_widgets: Dict[str, PluginRowWidget] = {}
        self._all_records: Dict[str, PluginRecord] = {}

        self._init_window_properties()
        self._init_ui()
        self.setStyleSheet(get_stylesheet())
        self.refresh_plugins()

    def _init_window_properties(self):
        self.setWindowTitle("Caster Plugin Manager")
        self.resize(self._DEFAULT_WIDTH, self._DEFAULT_HEIGHT)
        self.setMinimumSize(640, 400)

        # Set always on top hint for quick desktop access over editors
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.WindowStaysOnTopHint)

    def _init_ui(self):
        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(16, 16, 16, 12)
        root_layout.setSpacing(12)

        # 1. Header & Search Toolbar
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setSpacing(10)

        self._search_input = QtWidgets.QLineEdit(self)
        self._search_input.setPlaceholderText("Filter plugins by name, description, author... (Ctrl+F)")
        self._search_input.textChanged.connect(self._on_filter_changed)
        header_layout.addWidget(self._search_input, stretch=1)

        self._refresh_btn = QtWidgets.QPushButton("Refresh (F5)", self)
        self._refresh_btn.clicked.connect(self.refresh_plugins)
        header_layout.addWidget(self._refresh_btn)

        self._close_btn = QtWidgets.QPushButton("Close (Esc)", self)
        self._close_btn.clicked.connect(self.close)
        header_layout.addWidget(self._close_btn)

        root_layout.addLayout(header_layout)

        # 2. Main Content Split View (List on left, Tabbed Inspector on right)
        main_split_layout = QtWidgets.QHBoxLayout()
        main_split_layout.setSpacing(12)

        # Left Column: Plugin List
        self._list_widget = QtWidgets.QListWidget(self)
        self._list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self._list_widget.currentItemChanged.connect(self._on_list_selection_changed)
        main_split_layout.addWidget(self._list_widget, stretch=3)

        # Right Column: Tabbed Inspector (Overview + Settings)
        self._tabs = QtWidgets.QTabWidget(self)
        self._detail_pane = DetailPane(self)
        self._settings_form = SettingsFormWidget(config_store=self._registry.config_store, parent=self)

        self._tabs.addTab(self._detail_pane, "Overview")
        self._tabs.addTab(self._settings_form, "Settings")
        main_split_layout.addWidget(self._tabs, stretch=3)

        root_layout.addLayout(main_split_layout, stretch=1)

        # 3. Footer Status Bar
        footer_layout = QtWidgets.QHBoxLayout()
        self._footer_label = QtWidgets.QLabel(self)
        self._footer_label.setObjectName("footerStatus")
        footer_layout.addWidget(self._footer_label)
        footer_layout.addStretch()

        root_layout.addLayout(footer_layout)

    def refresh_plugins(self):
        """Forces a full filesystem scan and refreshes list entries."""
        selected_name = None
        current_item = self._list_widget.currentItem()
        if current_item:
            selected_name = current_item.data(QtCore.Qt.UserRole)

        self._all_records = self._registry.scan()
        self._settings_form.set_config_store(self._registry.config_store)
        self._populate_list(selected_name)
        self._update_footer_status()

    def _populate_list(self, previously_selected_name: Optional[str] = None):
        """Populates the QListWidget based on current search filter."""
        filter_text = self._search_input.text().strip().lower()
        self._list_widget.clear()
        self._row_widgets.clear()

        item_to_select = None

        for name, record in sorted(self._all_records.items()):
            meta = record.metadata
            searchable_text = f"{name} {meta.description} {meta.author}".lower()
            if filter_text and filter_text not in searchable_text:
                continue

            list_item = QtWidgets.QListWidgetItem(self._list_widget)
            list_item.setData(QtCore.Qt.UserRole, name)

            row_widget = PluginRowWidget(record, parent=self._list_widget)
            row_widget.toggled.connect(self._on_plugin_toggled)
            self._row_widgets[name] = row_widget

            list_item.setSizeHint(row_widget.sizeHint())
            self._list_widget.addItem(list_item)
            self._list_widget.setItemWidget(list_item, row_widget)

            if previously_selected_name and name == previously_selected_name:
                item_to_select = list_item

        if item_to_select:
            self._list_widget.setCurrentItem(item_to_select)
        elif self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)
        else:
            self._detail_pane.clear()
            self._settings_form.clear()
            self._tabs.setTabText(1, "Settings")

    def _on_filter_changed(self):
        selected_name = None
        current_item = self._list_widget.currentItem()
        if current_item:
            selected_name = current_item.data(QtCore.Qt.UserRole)
        self._populate_list(selected_name)

    def _on_list_selection_changed(self, current: Optional[QtWidgets.QListWidgetItem], previous: Optional[QtWidgets.QListWidgetItem]):
        if not current:
            self._detail_pane.clear()
            self._settings_form.clear()
            self._tabs.setTabText(1, "Settings")
            return

        plugin_name = current.data(QtCore.Qt.UserRole)
        record = self._all_records.get(plugin_name)
        self._detail_pane.set_plugin(record)
        self._settings_form.set_plugin(record)

        # Update tab label with option count
        opt_count = len(record.metadata.options) if (record and record.metadata.options) else 0
        tab_label = f"Settings ({opt_count})" if opt_count > 0 else "Settings"
        self._tabs.setTabText(1, tab_label)

    def _on_plugin_toggled(self, plugin_name: str, new_state: bool):
        """Handles toggle switch event from child row widget."""
        try:
            updated_record = self._registry.set_enabled(plugin_name, new_state)
            self._all_records[plugin_name] = updated_record

            # Update row widget in place
            if plugin_name in self._row_widgets:
                self._row_widgets[plugin_name].update_record(updated_record)

            # Update detail pane if currently selected
            current_item = self._list_widget.currentItem()
            if current_item and current_item.data(QtCore.Qt.UserRole) == plugin_name:
                self._detail_pane.set_plugin(updated_record)

            self._update_footer_status()
        except Exception as ex:
            QtWidgets.QMessageBox.warning(
                self,
                "Plugin State Error",
                f"Failed to update plugin '{plugin_name}': {ex}",
            )

    def _update_footer_status(self):
        total = len(self._all_records)
        enabled = sum(1 for r in self._all_records.values() if r.enabled)
        ready = sum(1 for r in self._all_records.values() if r.health == PluginHealthState.READY)
        issues = sum(
            1
            for r in self._all_records.values()
            if r.health
            in (
                PluginHealthState.MISSING_DEPENDENCIES,
                PluginHealthState.INCOMPATIBLE_PLATFORM,
                PluginHealthState.MALFORMED_METADATA,
                PluginHealthState.LOAD_ERROR,
            )
        )
        self._footer_label.setText(
            f"Total: {total} installed  |  Enabled: {enabled}  |  Ready: {ready}  |  Issues: {issues}"
        )

    def keyPressEvent(self, event: QtGui.QKeyEvent):
        """Handles keyboard navigation shortcuts."""
        key = event.key()

        # Escape closes window
        if key == QtCore.Qt.Key_Escape:
            self.close()
            return

        # F5 refreshes
        if key == QtCore.Qt.Key_F5 or (event.modifiers() == QtCore.Qt.ControlModifier and key == QtCore.Qt.Key_R):
            self.refresh_plugins()
            return

        # Ctrl+F focuses search
        if event.modifiers() == QtCore.Qt.ControlModifier and key == QtCore.Qt.Key_F:
            self._search_input.setFocus()
            self._search_input.selectAll()
            return

        # Space toggles active selection
        if key == QtCore.Qt.Key_Space:
            current_item = self._list_widget.currentItem()
            if current_item and not self._search_input.hasFocus():
                plugin_name = current_item.data(QtCore.Qt.UserRole)
                record = self._all_records.get(plugin_name)
                if record and record.health in (PluginHealthState.READY, PluginHealthState.DISABLED):
                    self._on_plugin_toggled(plugin_name, not record.enabled)
                    return

        super().keyPressEvent(event)
