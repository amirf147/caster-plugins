"""
HUD Commands and Voice Shortcut Help Window.
Compatible with Python 2.7 and Python 3.x.
"""

from castervoice.lib.qt import QtCore, QtGui, QtWidgets, qt_attr
from hud.theming.theme_manager import ThemeManager, THEME_CLASSIC

WINDOW_STAYS_ON_TOP_HINT = qt_attr(QtCore, ("Qt", "WindowStaysOnTopHint"), ("Qt", "WindowType", "WindowStaysOnTopHint"))
TOOL_WINDOW_HINT = qt_attr(QtCore, ("Qt", "Tool"), ("Qt", "WindowType", "Tool"))


class HelpDialog(QtWidgets.QWidget):
    """
    Standalone styled dialog displaying organized Caster HUD voice commands.
    """

    _WIDTH = 600
    _HEIGHT = 520

    def __init__(self, theme_name=THEME_CLASSIC, use_tray=False):
        flags = WINDOW_STAYS_ON_TOP_HINT
        if use_tray:
            flags |= TOOL_WINDOW_HINT
        QtWidgets.QWidget.__init__(self, f=flags)

        self.setGeometry(100, 200, HelpDialog._WIDTH, HelpDialog._HEIGHT)
        self.setWindowTitle("Caster HUD - Commands & Help")
        self.setStyleSheet(ThemeManager.get_stylesheet(theme_name))

        layout = QtWidgets.QVBoxLayout()
        help_view = QtWidgets.QTextEdit()
        help_view.setReadOnly(True)
        help_view.setFont(QtGui.QFont("Segoe UI", 9))

        help_html = """
        <style>
            h3 { color: #3498db; margin-bottom: 2px; margin-top: 10px; }
            table { width: 100%; border-collapse: collapse; margin-bottom: 12px; }
            th { text-align: left; color: #60a5fa; border-bottom: 1px solid #374151; padding: 4px; font-weight: bold; }
            td { padding: 4px; border-bottom: 1px solid rgba(255,255,255,10); }
            code { color: #f59e0b; font-weight: bold; }
        </style>
        <h3>Visibility & Window Controls</h3>
        <table>
            <tr><th>Voice Command / Hotkey</th><th>Description</th></tr>
            <tr><td><code>show caster hud</code></td><td>Opens or restores the HUD window</td></tr>
            <tr><td><code>hide caster hud</code></td><td>Docks HUD into system tray / hides overlay</td></tr>
            <tr><td><code>clear caster hud</code></td><td>Clears HUD text output stream</td></tr>
            <tr><td><code>show caster rules</code></td><td>Opens active Dragonfly grammars inspector</td></tr>
            <tr><td><code>caster hud border toggle [T]</code></td><td>Toggles title bar / frameless overlay</td></tr>
            <tr><td><code>caster hud drag toggle [D]</code></td><td>Toggles mouse & arrow key drag mode (turns Amber)</td></tr>
        </table>

        <h3>Panels & Verbose Status Display</h3>
        <table>
            <tr><th>Voice Command</th><th>Description</th></tr>
            <tr><td><code>caster hud status [toggle]</code></td><td>Toggles verbose top status header (Listening pill, Active window, Last rule)</td></tr>
            <tr><td><code>caster hud verbose [toggle]</code></td><td>Toggles verbose top status header</td></tr>
            <tr><td><code>caster hud active rules [toggle]</code></td><td>Toggles active grammar rules tag strip</td></tr>
            <tr><td><code>caster hud scroll [toggle]</code></td><td>Toggles vertical scrollbar on/off</td></tr>
        </table>

        <h3>Themes & Appearance</h3>
        <table>
            <tr><th>Voice Command</th><th>Description</th></tr>
            <tr><td><code>caster hud theme</code></td><td>Cycles through available themes</td></tr>
            <tr><td><code>caster hud theme classic</code></td><td>Original upstream classic light theme</td></tr>
            <tr><td><code>caster hud theme frosted</code></td><td>Modern acrylic dark theme</td></tr>
            <tr><td><code>caster hud theme minimal</code></td><td>Pitch black/translucent floating overlay</td></tr>
            <tr><td><code>caster hud theme high contrast</code></td><td>Pure black with bold high-contrast text</td></tr>
        </table>

        <h3>Font Sizing</h3>
        <table>
            <tr><th>Voice Command</th><th>Description</th></tr>
            <tr><td><code>caster hud font increase</code></td><td>Increases font size by 1pt</td></tr>
            <tr><td><code>caster hud font decrease</code></td><td>Decreases font size by 1pt</td></tr>
            <tr><td><code>caster hud font reset</code></td><td>Resets font size to default 9pt</td></tr>
        </table>

        <h3>Profiles & Layouts</h3>
        <table>
            <tr><th>Voice Command / Key</th><th>Description</th></tr>
            <tr><td><code>caster hud save profile [Enter]</code></td><td>Saves current geometry and theme layout</td></tr>
            <tr><td><code>show caster profiles [L]</code></td><td>Opens Profile Manager dialog</td></tr>
        </table>
        """
        help_view.setHtml(help_html)
        layout.addWidget(help_view)

        close_btn = QtWidgets.QPushButton("Close [Esc]")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def keyPressEvent(self, event):
        key_esc = qt_attr(QtCore, ("Qt", "Key_Escape"), ("Qt", "Key", "Key_Escape"))
        if event.key() == key_esc:
            self.close()
            event.accept()
            return
        QtWidgets.QWidget.keyPressEvent(self, event)
