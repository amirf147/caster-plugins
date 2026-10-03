# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Dynamic settings form generator widget for configurable plugin parameters.
"""

from typing import Any, Dict, Optional

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

from ...core.config_store import PluginConfigStore
from ...core.models import PluginRecord
from ...core.options import OptionDefinition, OptionType
from ..theme import (
    COLOR_BORDER,
    COLOR_HEALTH_ERROR,
    COLOR_HEALTH_READY,
    COLOR_TEXT_MUTED,
    COLOR_TEXT_PRIMARY,
)


class SettingsFormWidget(QtWidgets.QFrame):
    """
    Form inspector widget dynamically generating input controls for a plugin's declared options.
    """

    config_saved = Signal(str, dict)

    def __init__(
        self,
        config_store: Optional[PluginConfigStore] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.setObjectName("detailFrame")
        self._config_store = config_store or PluginConfigStore()
        self._current_record: Optional[PluginRecord] = None
        self._controls: Dict[str, Any] = {}

        self._init_ui()
        self.clear()

    def _init_ui(self):
        self._main_layout = QtWidgets.QVBoxLayout(self)
        self._main_layout.setContentsMargins(16, 16, 16, 16)
        self._main_layout.setSpacing(12)

        # Header Title
        self._title_label = QtWidgets.QLabel(self)
        self._title_label.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {COLOR_TEXT_PRIMARY};"
        )
        self._main_layout.addWidget(self._title_label)

        # Divider
        divider = QtWidgets.QFrame(self)
        divider.setFrameShape(QtWidgets.QFrame.HLine)
        divider.setStyleSheet(
            f"color: {COLOR_BORDER}; background-color: {COLOR_BORDER}; max-height: 1px;"
        )
        self._main_layout.addWidget(divider)

        # Scrollable form container
        self._scroll_area = QtWidgets.QScrollArea(self)
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._scroll_area.setStyleSheet("background: transparent;")

        self._form_container = QtWidgets.QWidget()
        self._form_layout = QtWidgets.QFormLayout(self._form_container)
        self._form_layout.setSpacing(10)
        self._form_layout.setLabelAlignment(QtCore.Qt.AlignLeft)
        self._scroll_area.setWidget(self._form_container)

        self._main_layout.addWidget(self._scroll_area, stretch=1)

        # Empty state message label
        self._empty_label = QtWidgets.QLabel(
            "No configurable options declared for this plugin.", self
        )
        self._empty_label.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; font-style: italic;")
        self._main_layout.addWidget(self._empty_label)

        # Status feedback label
        self._status_label = QtWidgets.QLabel(self)
        self._status_label.setStyleSheet("font-size: 11px;")
        self._main_layout.addWidget(self._status_label)
        self._status_label.hide()

        # Action Buttons Footer
        self._btn_layout = QtWidgets.QHBoxLayout()
        self._reset_btn = QtWidgets.QPushButton("Reset to Defaults", self)
        self._reset_btn.clicked.connect(self._on_reset_clicked)
        self._btn_layout.addWidget(self._reset_btn)

        self._btn_layout.addStretch()

        self._save_btn = QtWidgets.QPushButton("Save Settings", self)
        self._save_btn.setObjectName("primaryButton")
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._btn_layout.addWidget(self._save_btn)

        self._main_layout.addLayout(self._btn_layout)

    def set_config_store(self, config_store: PluginConfigStore):
        """Sets or replaces the active configuration store."""
        self._config_store = config_store

    def set_plugin(self, record: Optional[PluginRecord]):
        """Populates form controls for the specified plugin record."""
        self._current_record = record
        self._status_label.hide()

        if record is None:
            self.clear()
            return

        plugin_name = record.metadata.name
        options = record.metadata.options

        self._title_label.setText(f"{plugin_name} Configuration")

        # Clear existing controls from form layout
        self._clear_form_layout()
        self._controls.clear()

        if not options:
            self._scroll_area.hide()
            self._empty_label.show()
            self._reset_btn.setEnabled(False)
            self._save_btn.setEnabled(False)
            return

        self._empty_label.hide()
        self._scroll_area.show()
        self._reset_btn.setEnabled(True)
        self._save_btn.setEnabled(True)

        current_config = self._config_store.get_plugin_config(plugin_name, options)

        for opt_name, defn in options.items():
            current_val = current_config.get(opt_name, defn.default)
            label_text = f"<b>{opt_name}</b>"
            if defn.description:
                label_text += f"<br><span style='color:{COLOR_TEXT_MUTED};font-size:10px;'>{defn.description}</span>"

            label = QtWidgets.QLabel(label_text, self._form_container)
            label.setWordWrap(True)

            control = self._create_control_widget(defn, current_val)
            self._controls[opt_name] = (defn, control)
            self._form_layout.addRow(label, control)

    def _create_control_widget(
        self, defn: OptionDefinition, current_val: Any
    ) -> QtWidgets.QWidget:
        """Factory creating the appropriate Qt input widget for an OptionDefinition."""
        opt_type = defn.option_type

        if opt_type == OptionType.BOOL:
            chk = QtWidgets.QCheckBox(self._form_container)
            chk.setChecked(bool(current_val))
            return chk

        elif opt_type == OptionType.INT:
            spin = QtWidgets.QSpinBox(self._form_container)
            min_v = int(defn.min_value) if defn.min_value is not None else -2147483648
            max_v = int(defn.max_value) if defn.max_value is not None else 2147483647
            step_v = int(defn.step) if defn.step is not None else 1
            spin.setRange(min_v, max_v)
            spin.setSingleStep(step_v)
            spin.setValue(int(current_val) if current_val is not None else 0)
            return spin

        elif opt_type == OptionType.FLOAT:
            dspin = QtWidgets.QDoubleSpinBox(self._form_container)
            min_v = float(defn.min_value) if defn.min_value is not None else -1e9
            max_v = float(defn.max_value) if defn.max_value is not None else 1e9
            step_v = float(defn.step) if defn.step is not None else 0.1
            dspin.setRange(min_v, max_v)
            dspin.setSingleStep(step_v)
            dspin.setValue(float(current_val) if current_val is not None else 0.0)
            return dspin

        elif opt_type == OptionType.CHOICE:
            combo = QtWidgets.QComboBox(self._form_container)
            for choice in defn.choices:
                combo.addItem(choice)
            idx = combo.findText(str(current_val))
            if idx >= 0:
                combo.setCurrentIndex(idx)
            return combo

        elif opt_type == OptionType.PATH:
            container = QtWidgets.QWidget(self._form_container)
            box_layout = QtWidgets.QHBoxLayout(container)
            box_layout.setContentsMargins(0, 0, 0, 0)
            box_layout.setSpacing(6)

            line_edit = QtWidgets.QLineEdit(container)
            line_edit.setText(str(current_val) if current_val is not None else "")
            box_layout.addWidget(line_edit, stretch=1)

            browse_btn = QtWidgets.QPushButton("Browse...", container)
            browse_btn.clicked.connect(lambda: self._browse_path(line_edit))
            box_layout.addWidget(browse_btn)

            return container

        else:  # STRING
            line = QtWidgets.QLineEdit(self._form_container)
            line.setText(str(current_val) if current_val is not None else "")
            return line

    def _browse_path(self, line_edit: QtWidgets.QLineEdit):
        """Opens file/directory dialog and populates QLineEdit."""
        chosen_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Directory", line_edit.text()
        )
        if chosen_dir:
            line_edit.setText(chosen_dir)

    def _get_control_value(self, defn: OptionDefinition, control: QtWidgets.QWidget) -> Any:
        """Extracts current value from an input widget."""
        opt_type = defn.option_type

        if opt_type == OptionType.BOOL:
            return control.isChecked() if isinstance(control, QtWidgets.QCheckBox) else False
        elif opt_type == OptionType.INT:
            return control.value() if isinstance(control, QtWidgets.QSpinBox) else 0
        elif opt_type == OptionType.FLOAT:
            return control.value() if isinstance(control, QtWidgets.QDoubleSpinBox) else 0.0
        elif opt_type == OptionType.CHOICE:
            return control.currentText() if isinstance(control, QtWidgets.QComboBox) else ""
        elif opt_type == OptionType.PATH:
            line_edit = control.findChild(QtWidgets.QLineEdit)
            return line_edit.text().strip() if line_edit else ""
        else:  # STRING
            return control.text().strip() if isinstance(control, QtWidgets.QLineEdit) else ""

    def _on_save_clicked(self):
        """Collects form values, validates, and flushes to config store."""
        if not self._current_record:
            return

        plugin_name = self._current_record.metadata.name
        options = self._current_record.metadata.options
        payload: Dict[str, Any] = {}

        for opt_name, (defn, control) in self._controls.items():
            payload[opt_name] = self._get_control_value(defn, control)

        try:
            saved_config = self._config_store.set_plugin_config(
                plugin_name, payload, options
            )
            self._status_label.setText(f"Settings saved successfully for {plugin_name}.")
            self._status_label.setStyleSheet(
                f"color: {COLOR_HEALTH_READY}; font-size: 11px; font-weight: bold;"
            )
            self._status_label.show()
            self.config_saved.emit(plugin_name, saved_config)
        except Exception as ex:
            self._status_label.setText(f"Error saving settings: {ex}")
            self._status_label.setStyleSheet(
                f"color: {COLOR_HEALTH_ERROR}; font-size: 11px; font-weight: bold;"
            )
            self._status_label.show()

    def _on_reset_clicked(self):
        """Resets configuration to schema defaults and refreshes controls."""
        if not self._current_record:
            return

        plugin_name = self._current_record.metadata.name
        options = self._current_record.metadata.options

        default_config = self._config_store.reset_plugin_config(plugin_name, options)

        for opt_name, (defn, control) in self._controls.items():
            default_val = default_config.get(opt_name, defn.default)
            self._set_control_value(defn, control, default_val)

        self._status_label.setText("Reset all options to default values.")
        self._status_label.setStyleSheet(
            f"color: {COLOR_HEALTH_READY}; font-size: 11px; font-weight: bold;"
        )
        self._status_label.show()
        self.config_saved.emit(plugin_name, default_config)

    def _set_control_value(
        self, defn: OptionDefinition, control: QtWidgets.QWidget, value: Any
    ):
        """Sets value on an input control widget."""
        opt_type = defn.option_type
        if opt_type == OptionType.BOOL and isinstance(control, QtWidgets.QCheckBox):
            control.setChecked(bool(value))
        elif opt_type == OptionType.INT and isinstance(control, QtWidgets.QSpinBox):
            control.setValue(int(value) if value is not None else 0)
        elif opt_type == OptionType.FLOAT and isinstance(control, QtWidgets.QDoubleSpinBox):
            control.setValue(float(value) if value is not None else 0.0)
        elif opt_type == OptionType.CHOICE and isinstance(control, QtWidgets.QComboBox):
            idx = control.findText(str(value))
            if idx >= 0:
                control.setCurrentIndex(idx)
        elif opt_type == OptionType.PATH:
            line_edit = control.findChild(QtWidgets.QLineEdit)
            if line_edit:
                line_edit.setText(str(value) if value is not None else "")
        elif isinstance(control, QtWidgets.QLineEdit):
            control.setText(str(value) if value is not None else "")

    def _clear_form_layout(self):
        """Removes all widget rows from form layout."""
        while self._form_layout.count() > 0:
            item = self._form_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def clear(self):
        """Resets form to empty unselected state."""
        self._current_record = None
        self._title_label.setText("Plugin Configuration")
        self._clear_form_layout()
        self._controls.clear()
        self._scroll_area.hide()
        self._empty_label.show()
        self._empty_label.setText("Select a plugin to configure its options.")
        self._status_label.hide()
        self._reset_btn.setEnabled(False)
        self._save_btn.setEnabled(False)
