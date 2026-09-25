"""
Interactive Theme Customizer & Appearance Settings Dialog.
Provides visual theme selection, custom theme creation with QColorDialog pickers,
and a real-time HUD window transparency slider.
Compatible with Python 2.7 and Python 3.x (PySide2/PySide6).
"""

from castervoice.lib.qt import QtCore, QtGui, QtWidgets, qt_attr
from hud.theming.theme_manager import (
    ThemeManager,
    THEME_CLASSIC,
    THEME_FROSTED,
)

WINDOW_STAYS_ON_TOP_HINT = qt_attr(QtCore, ("Qt", "WindowStaysOnTopHint"), ("Qt", "WindowType", "WindowStaysOnTopHint"))
TOOL_WINDOW_HINT = qt_attr(QtCore, ("Qt", "Tool"), ("Qt", "WindowType", "Tool"))
HORIZONTAL_ORIENTATION = qt_attr(QtCore, ("Qt", "Horizontal"), ("Qt", "Orientation", "Horizontal"))

COLOR_KEYS = [
    ("background_color", "Window Background"),
    ("textedit_bg", "Log Background"),
    ("text_color", "Text Color"),
    ("accent_color", "Accent / Selection"),
    ("border_color", "Border / Divider"),
    ("cmd_color", "Command Text (<)"),
    ("sys_color", "System Text (>)"),
    ("err_color", "Error Text (>)"),
]


class ThemeCustomizerDialog(QtWidgets.QWidget):
    """
    Dialog for customizing HUD themes, editing colors, and adjusting transparency.
    """

    _WIDTH = 480
    _HEIGHT = 580

    def __init__(self, main_window, theme_name=THEME_CLASSIC, use_tray=False):
        flags = WINDOW_STAYS_ON_TOP_HINT
        if use_tray:
            flags |= TOOL_WINDOW_HINT
        QtWidgets.QWidget.__init__(self, f=flags)
        self.main_window = main_window
        self._current_theme_id = theme_name
        self._is_updating_ui = False
        self._color_swatches = {}
        self._color_edits = {}

        self.setGeometry(120, 180, self._WIDTH, self._HEIGHT)
        self.setWindowTitle("Customize HUD & Themes")
        self.setStyleSheet(ThemeManager.get_stylesheet(theme_name))

        root_layout = QtWidgets.QVBoxLayout()
        root_layout.setSpacing(10)
        root_layout.setContentsMargins(14, 14, 14, 14)

        # 1. Header Banner
        header = QtWidgets.QLabel("<b>HUD Customize & Themes</b>")
        subtitle = QtWidgets.QLabel(
            "Select a preset theme, create custom palettes, configure colors, and adjust transparency."
        )
        subtitle.setWordWrap(True)
        root_layout.addWidget(header)
        root_layout.addWidget(subtitle)

        # 2. Theme Selection Row
        theme_sel_box = QtWidgets.QGroupBox("Theme Selection")
        theme_sel_layout = QtWidgets.QVBoxLayout()

        combo_row = QtWidgets.QHBoxLayout()
        combo_row.addWidget(QtWidgets.QLabel("Active Theme:"))
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.currentIndexChanged.connect(self._on_theme_combo_changed)
        combo_row.addWidget(self.theme_combo, 1)

        self.new_btn = QtWidgets.QPushButton("New Theme")
        self.new_btn.setToolTip("Create a new custom theme based on current palette")
        self.new_btn.clicked.connect(self._on_new_theme_clicked)
        combo_row.addWidget(self.new_btn)

        self.del_btn = QtWidgets.QPushButton("Delete")
        self.del_btn.setToolTip("Delete selected custom theme")
        self.del_btn.clicked.connect(self._on_delete_theme_clicked)
        combo_row.addWidget(self.del_btn)
        theme_sel_layout.addLayout(combo_row)

        name_row = QtWidgets.QHBoxLayout()
        name_row.addWidget(QtWidgets.QLabel("Theme Name:"))
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.textChanged.connect(self._on_name_changed)
        name_row.addWidget(self.name_edit, 1)
        theme_sel_layout.addLayout(name_row)

        theme_sel_box.setLayout(theme_sel_layout)
        root_layout.addWidget(theme_sel_box)

        # 3. Colors Configuration Group
        colors_box = QtWidgets.QGroupBox("Theme Colors")
        colors_grid = QtWidgets.QGridLayout()
        colors_grid.setSpacing(8)

        row = 0
        for key, label_text in COLOR_KEYS:
            lbl = QtWidgets.QLabel(label_text + ":")
            lbl.setMinimumWidth(130)

            swatch_btn = QtWidgets.QPushButton()
            swatch_btn.setFixedSize(50, 24)
            swatch_btn.setCursor(qt_attr(QtCore, ("Qt", "PointingHandCursor"), ("Qt", "CursorShape", "PointingHandCursor")))
            swatch_btn.setToolTip("Click to select color with color picker")
            swatch_btn.clicked.connect(lambda checked=False, k=key: self._pick_color(k))
            self._color_swatches[key] = swatch_btn

            hex_edit = QtWidgets.QLineEdit()
            hex_edit.setMaximumWidth(90)
            hex_edit.textEdited.connect(lambda text, k=key: self._on_hex_edited(k, text))
            self._color_edits[key] = hex_edit

            colors_grid.addWidget(lbl, row, 0)
            colors_grid.addWidget(swatch_btn, row, 1)
            colors_grid.addWidget(hex_edit, row, 2)
            row += 1

        colors_box.setLayout(colors_grid)
        root_layout.addWidget(colors_box)

        # 4. Transparency & Opacity Sliders (Background & Letter/Text)
        trans_box = QtWidgets.QGroupBox("HUD Transparency & Opacity")
        trans_layout = QtWidgets.QVBoxLayout()
        trans_layout.setSpacing(8)

        # Background Opacity Slider
        bg_header_row = QtWidgets.QHBoxLayout()
        bg_header_row.addWidget(QtWidgets.QLabel("Background Opacity:"))
        self.bg_opacity_label = QtWidgets.QLabel("100%")
        self.bg_opacity_label.setAlignment(qt_attr(QtCore, ("Qt", "AlignRight"), ("Qt", "AlignmentFlag", "AlignRight")))
        bg_header_row.addWidget(self.bg_opacity_label)
        trans_layout.addLayout(bg_header_row)

        self.bg_opacity_slider = QtWidgets.QSlider(HORIZONTAL_ORIENTATION)
        self.bg_opacity_slider.setRange(10, 100)
        self.bg_opacity_slider.setSingleStep(5)
        self.bg_opacity_slider.setPageStep(10)
        self.bg_opacity_slider.setValue(100)
        self.bg_opacity_slider.valueChanged.connect(self._on_bg_opacity_slider_changed)
        trans_layout.addWidget(self.bg_opacity_slider)

        # Letter / Text Opacity Slider
        text_header_row = QtWidgets.QHBoxLayout()
        text_header_row.addWidget(QtWidgets.QLabel("Letter / Text Opacity:"))
        self.text_opacity_label = QtWidgets.QLabel("100%")
        self.text_opacity_label.setAlignment(qt_attr(QtCore, ("Qt", "AlignRight"), ("Qt", "AlignmentFlag", "AlignRight")))
        text_header_row.addWidget(self.text_opacity_label)
        trans_layout.addLayout(text_header_row)

        self.text_opacity_slider = QtWidgets.QSlider(HORIZONTAL_ORIENTATION)
        self.text_opacity_slider.setRange(10, 100)
        self.text_opacity_slider.setSingleStep(5)
        self.text_opacity_slider.setPageStep(10)
        self.text_opacity_slider.setValue(100)
        self.text_opacity_slider.valueChanged.connect(self._on_text_opacity_slider_changed)
        trans_layout.addWidget(self.text_opacity_slider)

        # Backwards compatibility alias
        self.opacity_slider = self.bg_opacity_slider
        self.opacity_label = self.bg_opacity_label

        trans_box.setLayout(trans_layout)
        root_layout.addWidget(trans_box)

        # 5. Text Alignment Selection
        align_box = QtWidgets.QGroupBox("HUD Text Alignment")
        align_layout = QtWidgets.QHBoxLayout()
        self.align_left_radio = QtWidgets.QRadioButton("Left Aligned")
        self.align_right_radio = QtWidgets.QRadioButton("Right Aligned")
        self.align_left_radio.setChecked(True)
        self.align_left_radio.toggled.connect(self._on_alignment_radio_toggled)
        self.align_right_radio.toggled.connect(self._on_alignment_radio_toggled)
        align_layout.addWidget(self.align_left_radio)
        align_layout.addWidget(self.align_right_radio)
        align_box.setLayout(align_layout)
        root_layout.addWidget(align_box)

        # 6. Bottom Action Buttons Bar
        btn_row = QtWidgets.QHBoxLayout()

        self.save_btn = QtWidgets.QPushButton("Save Theme [Enter]")
        self.save_btn.clicked.connect(self._do_save)
        btn_row.addWidget(self.save_btn)

        self.apply_btn = QtWidgets.QPushButton("Apply")
        self.apply_btn.clicked.connect(self._do_apply)
        btn_row.addWidget(self.apply_btn)

        self.reset_btn = QtWidgets.QPushButton("Reset")
        self.reset_btn.setToolTip("Revert colors and opacity to the selected preset defaults")
        self.reset_btn.clicked.connect(self._do_reset)
        btn_row.addWidget(self.reset_btn)

        self.close_btn = QtWidgets.QPushButton("Close [Esc]")
        self.close_btn.clicked.connect(self.close)
        btn_row.addWidget(self.close_btn)

        root_layout.addLayout(btn_row)
        self.setLayout(root_layout)

        # Initial populate
        self._populate_themes_combo(select_theme=theme_name)
        initial_bg = getattr(main_window.state, "background_opacity", getattr(main_window.state, "opacity", 1.0))
        initial_txt = getattr(main_window.state, "text_opacity", 1.0)
        self._set_opacity_ui(bg_opacity=initial_bg, text_opacity=initial_txt)
        initial_align = getattr(main_window.state, "text_alignment", "left")
        self._set_alignment_ui(initial_align)

    def _populate_themes_combo(self, select_theme=None):
        """Populate the themes dropdown with built-ins and custom palettes."""
        self._is_updating_ui = True
        self.theme_combo.clear()

        available = ThemeManager.get_available_themes()
        target_idx = 0
        norm_select = ThemeManager.normalize_theme_name(select_theme or self._current_theme_id)

        for i, th in enumerate(available):
            is_built = ThemeManager.is_builtin_theme(th)
            display = th.replace("-", " ").title()
            if is_built:
                display += " (Built-in)"
            self.theme_combo.addItem(display, th)
            if th == norm_select:
                target_idx = i

        self.theme_combo.setCurrentIndex(target_idx)
        self._is_updating_ui = False
        self._load_theme_into_ui(available[target_idx] if available else THEME_CLASSIC)

    def _load_theme_into_ui(self, theme_id):
        """Loads color and metadata of the specified theme into the editor fields."""
        self._is_updating_ui = True
        self._current_theme_id = theme_id
        data = ThemeManager.get_theme_data(theme_id)

        is_builtin = ThemeManager.is_builtin_theme(theme_id)
        display_name = data.get("name", theme_id.replace("-", " ").title())
        self.name_edit.setText(display_name)
        self.name_edit.setReadOnly(is_builtin)
        self.del_btn.setEnabled(not is_builtin)

        for key, _ in COLOR_KEYS:
            val = data.get(key, "#1e1e24")
            self._color_edits[key].setText(val)
            self._update_swatch(key, val)

        bg_op = data.get("background_opacity", data.get("opacity", 1.0))
        txt_op = data.get("text_opacity", 1.0)
        self._set_opacity_ui(bg_opacity=float(bg_op), text_opacity=float(txt_op))
        align = data.get("text_alignment", "left")
        self._set_alignment_ui(align)

        self._is_updating_ui = False

    def _update_swatch(self, key, hex_color):
        """Updates color preview button background."""
        btn = self._color_swatches.get(key)
        if btn:
            btn.setStyleSheet(
                "QPushButton {{ background-color: {0}; border: 1px solid #777; border-radius: 3px; }}".format(
                    hex_color
                )
            )

    def _set_opacity_ui(self, bg_opacity=None, text_opacity=None):
        """Sets sliders and text labels for background and letter opacity."""
        if bg_opacity is not None:
            pct_bg = max(10, min(100, int(round(float(bg_opacity) * 100))))
            self.bg_opacity_slider.setValue(pct_bg)
            self.bg_opacity_label.setText("{0}%".format(pct_bg))
        if text_opacity is not None:
            pct_txt = max(10, min(100, int(round(float(text_opacity) * 100))))
            self.text_opacity_slider.setValue(pct_txt)
            self.text_opacity_label.setText("{0}%".format(pct_txt))

    def _set_alignment_ui(self, alignment="left"):
        """Sets the active text alignment radio button ('left' or 'right')."""
        is_right = str(alignment).lower() == "right"
        self.align_right_radio.setChecked(is_right)
        self.align_left_radio.setChecked(not is_right)

    def _get_alignment_ui(self):
        """Returns currently selected text alignment ('left' or 'right')."""
        return "right" if self.align_right_radio.isChecked() else "left"

    def _on_alignment_radio_toggled(self, checked):
        """Applies alignment change live on HUD when radio button is selected."""
        if not self._is_updating_ui and checked:
            align = self._get_alignment_ui()
            if hasattr(self.main_window, "set_text_alignment"):
                self.main_window.set_text_alignment(align)

    def _pick_color(self, key):
        """Opens QColorDialog to choose color visually."""
        current_hex = self._color_edits[key].text().strip()
        initial_color = QtGui.QColor(current_hex) if QtGui.QColor(current_hex).isValid() else QtGui.QColor("#ffffff")
        chosen = QtWidgets.QColorDialog.getColor(initial_color, self, "Select Color")
        if chosen.isValid():
            hex_val = chosen.name()
            self._color_edits[key].setText(hex_val)
            self._update_swatch(key, hex_val)
            self._live_preview()

    def _on_hex_edited(self, key, text):
        """Responds to user manual hex code input."""
        cleaned = text.strip()
        if QtGui.QColor(cleaned).isValid():
            self._update_swatch(key, cleaned)
            self._live_preview()

    def _on_bg_opacity_slider_changed(self, value):
        """Adjusts background opacity in real-time on HUD window."""
        self.bg_opacity_label.setText("{0}%".format(value))
        opacity = value / 100.0
        self._live_preview()
        if hasattr(self.main_window, "set_background_opacity"):
            self.main_window.set_background_opacity(opacity)

    def _on_text_opacity_slider_changed(self, value):
        """Adjusts letter/text opacity in real-time on HUD window."""
        self.text_opacity_label.setText("{0}%".format(value))
        opacity = value / 100.0
        self._live_preview()
        if hasattr(self.main_window, "set_text_opacity"):
            self.main_window.set_text_opacity(opacity)

    def _on_opacity_slider_changed(self, value):
        """Backwards compatibility proxy for single slider calls."""
        self._on_bg_opacity_slider_changed(value)

    def _on_theme_combo_changed(self, index):
        """Fires when user chooses a different theme in the dropdown."""
        if self._is_updating_ui or index < 0:
            return
        theme_id = self.theme_combo.itemData(index)
        if theme_id:
            self._load_theme_into_ui(theme_id)
            if hasattr(self.main_window, "apply_theme"):
                self.main_window.apply_theme(theme_id)

    def _on_name_changed(self, text):
        pass

    def _on_new_theme_clicked(self):
        """Initializes a new custom theme draft based on the currently displayed colors."""
        self.name_edit.setReadOnly(False)
        base_name = self.name_edit.text().strip().replace(" (Built-in)", "")
        new_name = "Custom " + base_name if not base_name.startswith("Custom ") else base_name + " 2"
        self.name_edit.setText(new_name)
        self.name_edit.setFocus()
        self.name_edit.selectAll()
        self.del_btn.setEnabled(False)

    def _on_delete_theme_clicked(self):
        """Deletes the selected custom theme and falls back to classic or frosted-dark."""
        curr_idx = self.theme_combo.currentIndex()
        if curr_idx < 0:
            return
        theme_id = self.theme_combo.itemData(curr_idx)
        if not theme_id or ThemeManager.is_builtin_theme(theme_id):
            return

        success = ThemeManager.delete_custom_theme(theme_id)
        if success:
            fallback = THEME_FROSTED if THEME_FROSTED in ThemeManager.get_available_themes() else THEME_CLASSIC
            self._populate_themes_combo(select_theme=fallback)
            if hasattr(self.main_window, "apply_theme"):
                self.main_window.apply_theme(fallback)

    def _collect_form_data(self):
        """Gathers colors, opacities, and alignment into a theme dictionary."""
        bg_op = self.bg_opacity_slider.value() / 100.0
        txt_op = self.text_opacity_slider.value() / 100.0
        data = {
            "name": self.name_edit.text().strip() or "Custom Theme",
            "background_opacity": bg_op,
            "text_opacity": txt_op,
            "opacity": bg_op,
            "text_alignment": self._get_alignment_ui(),
        }
        for key, _ in COLOR_KEYS:
            val = self._color_edits[key].text().strip()
            data[key] = val if QtGui.QColor(val).isValid() else "#ffffff"
        return data

    def _live_preview(self):
        """Applies temporary live stylesheet to main window."""
        data = self._collect_form_data()
        from hud.theming.theme_manager import build_stylesheet
        stylesheet = build_stylesheet(data)
        if hasattr(self.main_window, "setStyleSheet"):
            self.main_window.setStyleSheet(stylesheet)
            self.setStyleSheet(stylesheet)

    def _do_apply(self):
        """Applies current settings without necessarily saving to a file."""
        self._live_preview()
        if hasattr(self.main_window, "set_background_opacity"):
            self.main_window.set_background_opacity(self.bg_opacity_slider.value() / 100.0)
        if hasattr(self.main_window, "set_text_opacity"):
            self.main_window.set_text_opacity(self.text_opacity_slider.value() / 100.0)
        if hasattr(self.main_window, "set_text_alignment"):
            self.main_window.set_text_alignment(self._get_alignment_ui())

    def _do_save(self):
        """Saves current palette as a custom theme and applies it permanently."""
        name = self.name_edit.text().strip()
        if not name:
            name = "Custom Theme"
        if ThemeManager.is_builtin_theme(name):
            name = "Custom " + name

        data = self._collect_form_data()
        saved_id = ThemeManager.save_custom_theme(name, data)

        # Refresh dropdown with new theme selected
        self._populate_themes_combo(select_theme=saved_id)

        # Apply to main window
        if hasattr(self.main_window, "apply_theme"):
            self.main_window.apply_theme(
                saved_id,
                background_opacity=data["background_opacity"],
                text_opacity=data["text_opacity"],
                text_alignment=data["text_alignment"],
            )
        if hasattr(self.main_window, "set_background_opacity"):
            self.main_window.set_background_opacity(data["background_opacity"])
        if hasattr(self.main_window, "set_text_opacity"):
            self.main_window.set_text_opacity(data["text_opacity"])
        if hasattr(self.main_window, "set_text_alignment"):
            self.main_window.set_text_alignment(data["text_alignment"])

        if hasattr(self.main_window, "log_widget"):
            self.main_window.log_widget.append_system_text(
                "Theme Saved: '{0}'".format(name), saved_id
            )

    def _do_reset(self):
        """Resets colors and opacity to the selected preset defaults."""
        curr_idx = self.theme_combo.currentIndex()
        if curr_idx >= 0:
            theme_id = self.theme_combo.itemData(curr_idx)
            self._load_theme_into_ui(theme_id)
            if hasattr(self.main_window, "apply_theme"):
                self.main_window.apply_theme(theme_id)

    def refresh_state(self, theme_name=None, background_opacity=None, text_opacity=None, text_alignment=None, opacity=None):
        """Refreshes the dialog fields when re-opened."""
        if theme_name:
            self._populate_themes_combo(select_theme=theme_name)
        bg = background_opacity if background_opacity is not None else opacity
        self._set_opacity_ui(bg_opacity=bg, text_opacity=text_opacity)
        if text_alignment is not None:
            self._set_alignment_ui(text_alignment)
        self.setStyleSheet(ThemeManager.get_stylesheet(self._current_theme_id))

    def show_dialog(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def keyPressEvent(self, event):
        key_esc = qt_attr(QtCore, ("Qt", "Key_Escape"), ("Qt", "Key", "Key_Escape"))
        key_enter = qt_attr(QtCore, ("Qt", "Key_Return"), ("Qt", "Key", "Key_Return"))
        key_enter_pad = qt_attr(QtCore, ("Qt", "Key_Enter"), ("Qt", "Key", "Key_Enter"))

        if event.key() == key_esc:
            self.close()
            event.accept()
            return
        if event.key() in (key_enter, key_enter_pad) and not self.name_edit.hasFocus():
            self._do_save()
            event.accept()
            return

        QtWidgets.QWidget.keyPressEvent(self, event)
