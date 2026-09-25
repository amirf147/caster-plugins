"""
Active Rules and Grammars Tree Inspection Dialog.
Compatible with Python 2.7 and Python 3.x.
"""

import json
from castervoice.lib.qt import QtCore, QtGui, QtWidgets, qt_attr
from hud.theming.theme_manager import ThemeManager, THEME_CLASSIC

WINDOW_STAYS_ON_TOP_HINT = qt_attr(QtCore, ("Qt", "WindowStaysOnTopHint"), ("Qt", "WindowType", "WindowStaysOnTopHint"))
TOOL_WINDOW_HINT = qt_attr(QtCore, ("Qt", "Tool"), ("Qt", "WindowType", "Tool"))


class RulesTreeDialog(QtWidgets.QWidget):
    """
    Dialog displaying active Dragonfly grammars, rules, and command specs.
    """

    _WIDTH = 600
    _MARGIN = 30

    def __init__(self, json_text="", theme_name=THEME_CLASSIC, use_tray=False):
        flags = WINDOW_STAYS_ON_TOP_HINT
        if use_tray:
            flags |= TOOL_WINDOW_HINT
        QtWidgets.QWidget.__init__(self, f=flags)

        try:
            import dragonfly
            x = dragonfly.monitors[0].rectangle.dx - (RulesTreeDialog._WIDTH + RulesTreeDialog._MARGIN)
            y = 300
            dx = RulesTreeDialog._WIDTH
            dy = max(300, dragonfly.monitors[0].rectangle.dy - (y + 2 * RulesTreeDialog._MARGIN))
            self.setGeometry(x, y, dx, dy)
        except Exception:
            self.setGeometry(100, 200, RulesTreeDialog._WIDTH, 400)

        self.setWindowTitle("Active Rules")
        self.setStyleSheet(ThemeManager.get_stylesheet(theme_name))

        rules_tree = QtGui.QStandardItemModel()
        rules_tree.setColumnCount(2)
        rules_tree.setHorizontalHeaderLabels(['phrase', 'action'])

        if json_text:
            try:
                rules_dict = json.loads(json_text)
                rules_root = rules_tree.invisibleRootItem()
                for g in rules_dict:
                    gram = QtGui.QStandardItem(g.get("name", "")) if len(g.get("rules", [])) > 1 else None
                    for r in g.get("rules", []):
                        rule = QtGui.QStandardItem(r.get("name", ""))
                        specs = r.get("specs", [])
                        rule.setRowCount(len(specs))
                        rule.setColumnCount(2)
                        row = 0
                        for s in specs:
                            phrase, _, action = s.partition('::')
                            rule.setChild(row, 0, QtGui.QStandardItem(phrase))
                            rule.setChild(row, 1, QtGui.QStandardItem(action))
                            row += 1
                        if gram is None:
                            rules_root.appendRow(rule)
                        else:
                            gram.appendRow(rule)
                    if gram:
                        rules_root.appendRow(gram)
            except Exception:
                pass

        tree_view = QtWidgets.QTreeView(self)
        tree_view.setModel(rules_tree)
        tree_view.setColumnWidth(0, RulesTreeDialog._WIDTH // 2)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(tree_view)
        self.setLayout(layout)

    def keyPressEvent(self, event):
        key_esc = qt_attr(QtCore, ("Qt", "Key_Escape"), ("Qt", "Key", "Key_Escape"))
        if event.key() == key_esc:
            self.close()
            event.accept()
            return
        QtWidgets.QWidget.keyPressEvent(self, event)
