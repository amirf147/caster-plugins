"""
Accessible Profile Manager Dialog.
Supports full keyboard interaction: Enter (Save), L (Load), R (Reset Default), Del (Delete), Esc (Close).
Compatible with Python 2.7 and Python 3.x.
"""

from castervoice.lib.qt import QtCore, QtGui, QtWidgets, qt_attr
from hud.theming.theme_manager import ThemeManager, THEME_CLASSIC

WINDOW_STAYS_ON_TOP_HINT = qt_attr(QtCore, ("Qt", "WindowStaysOnTopHint"), ("Qt", "WindowType", "WindowStaysOnTopHint"))
TOOL_WINDOW_HINT = qt_attr(QtCore, ("Qt", "Tool"), ("Qt", "WindowType", "Tool"))


class ProfileDialog(QtWidgets.QWidget):
    """
    Unified dialog for managing named HUD layout profiles.
    """

    _WIDTH = 400
    _HEIGHT = 320

    def __init__(self, main_window, profile_mgr, theme_name=THEME_CLASSIC, use_tray=False):
        flags = WINDOW_STAYS_ON_TOP_HINT
        if use_tray:
            flags |= TOOL_WINDOW_HINT
        QtWidgets.QWidget.__init__(self, f=flags)
        self.main_window = main_window
        self.profile_mgr = profile_mgr

        self.setGeometry(100, 200, ProfileDialog._WIDTH, ProfileDialog._HEIGHT)
        self.setWindowTitle("Caster HUD Profiles")
        self.setStyleSheet(ThemeManager.get_stylesheet(theme_name))

        layout = QtWidgets.QVBoxLayout()
        header = QtWidgets.QLabel("<b>Caster HUD Profile Manager</b>")
        layout.addWidget(header)

        info_lbl = QtWidgets.QLabel("Saved Profiles:")
        layout.addWidget(info_lbl)

        self.list_widget = QtWidgets.QListWidget()
        self._populate_profiles()
        self.list_widget.currentTextChanged.connect(self._on_profile_selected)
        layout.addWidget(self.list_widget)

        name_layout = QtWidgets.QHBoxLayout()
        name_layout.addWidget(QtWidgets.QLabel("Profile Name:"))
        self.name_edit = QtWidgets.QLineEdit("default")
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        btn_layout = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Save [Enter]")
        self.save_btn.clicked.connect(self._do_save)
        btn_layout.addWidget(self.save_btn)

        self.load_btn = QtWidgets.QPushButton("Load [L]")
        self.load_btn.clicked.connect(self._do_load)
        btn_layout.addWidget(self.load_btn)

        self.reset_btn = QtWidgets.QPushButton("Reset Default [R]")
        self.reset_btn.clicked.connect(self._do_reset_default)
        btn_layout.addWidget(self.reset_btn)

        self.del_btn = QtWidgets.QPushButton("Delete [Del]")
        self.del_btn.clicked.connect(self._do_delete)
        btn_layout.addWidget(self.del_btn)

        self.cancel_btn = QtWidgets.QPushButton("Close [Esc]")
        self.cancel_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def _populate_profiles(self):
        self.list_widget.clear()
        for p in self.profile_mgr.list_profiles():
            self.list_widget.addItem(p)

    def _on_profile_selected(self, text):
        if text:
            self.name_edit.setText(text)

    def _do_save(self):
        name = self.name_edit.text().strip()
        if name:
            self.main_window.save_named_profile(name)
        self.close()

    def _do_load(self):
        name = self.name_edit.text().strip()
        if not name and self.list_widget.currentItem():
            name = self.list_widget.currentItem().text().strip()
        if name:
            self.main_window.load_named_profile(name)
        self.close()

    def _do_reset_default(self):
        self.main_window.reset_to_default_profile()
        self._populate_profiles()

    def _do_delete(self):
        name = self.name_edit.text().strip()
        if not name and self.list_widget.currentItem():
            name = self.list_widget.currentItem().text().strip()
        if name:
            self.profile_mgr.delete_profile(name)
            self._populate_profiles()

    def show_dialog(self, mode="save"):
        self._populate_profiles()
        self.show()
        self.raise_()
        self.activateWindow()
        if mode == "save":
            self.name_edit.setFocus()
            self.name_edit.selectAll()
        else:
            self.list_widget.setFocus()

    def keyPressEvent(self, event):
        key_esc = qt_attr(QtCore, ("Qt", "Key_Escape"), ("Qt", "Key", "Key_Escape"))
        key_del = qt_attr(QtCore, ("Qt", "Key_Delete"), ("Qt", "Key", "Key_Delete"))
        key_enter = qt_attr(QtCore, ("Qt", "Key_Return"), ("Qt", "Key", "Key_Return"))
        key_enter_pad = qt_attr(QtCore, ("Qt", "Key_Enter"), ("Qt", "Key", "Key_Enter"))
        key_l = qt_attr(QtCore, ("Qt", "Key_L"), ("Qt", "Key", "Key_L"))
        key_r = qt_attr(QtCore, ("Qt", "Key_R"), ("Qt", "Key", "Key_R"))

        if event.key() == key_esc:
            self.close()
            event.accept()
            return
        if event.key() == key_del:
            self._do_delete()
            event.accept()
            return
        if event.key() in (key_enter, key_enter_pad):
            self._do_save()
            event.accept()
            return
        if event.key() == key_l and not self.name_edit.hasFocus():
            self._do_load()
            event.accept()
            return
        if event.key() == key_r and not self.name_edit.hasFocus():
            self._do_reset_default()
            event.accept()
            return
        QtWidgets.QWidget.keyPressEvent(self, event)
