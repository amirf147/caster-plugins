"""
Verbose Header Status Bar Widget.
Renders engine mode, active window context, and last executed voice rule.
Strictly decoupled from ADCE micro-context (which resides in AdceBarWidget).
Compatible with Python 2.7 and Python 3.x.
"""

from castervoice.lib.qt import QtWidgets, QtGui, QtCore
from hud.core import constants
from hud.core.state import HudState


class StatusBarWidget(QtWidgets.QWidget):
    """
    Verbose header status bar containing engine state pills, active window, and rule metadata.
    """

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.setFixedHeight(24)
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # 1. Engine Mic State Pill
        self._status_pill = QtWidgets.QLabel("LISTENING")
        self._status_pill.setStyleSheet(
            "background-color: {0}; color: #ffffff; "
            "font-weight: bold; font-size: 8pt; border-radius: 3px; padding: 1px 6px;".format(constants.COLOR_MIC_ON)
        )
        layout.addWidget(self._status_pill)

        # 2. Active Window / Process Context Label
        self._context_label = QtWidgets.QLabel("")
        self._context_label.setStyleSheet("color: #60a5fa; font-weight: bold; font-size: 8pt;")
        layout.addWidget(self._context_label)

        # 3. Active / Last Rule Pill
        self._rule_label = QtWidgets.QLabel("")
        self._rule_label.setStyleSheet("color: #a78bfa; font-size: 8pt;")
        layout.addWidget(self._rule_label)

        layout.addStretch()
        self.setLayout(layout)

    def update_state(self, state):
        """Updates status pill text and background color according to mic state and context."""
        status_text = state.get_status_text()
        self._status_pill.setText(status_text)
        
        bg_color = constants.COLOR_MIC_SLEEPING if state.mic_mode == "sleeping" else constants.COLOR_MIC_ON
        self._status_pill.setStyleSheet(
            "background-color: {0}; color: #ffffff; "
            "font-weight: bold; font-size: 8pt; border-radius: 3px; padding: 1px 6px;".format(bg_color)
        )

        # Context (Process / Window Title)
        ctx = state.desktop_context
        if ctx.window_title:
            title = ctx.window_title[:30] + "..." if len(ctx.window_title) > 30 else ctx.window_title
            self._context_label.setText(title)
        elif ctx.process_name:
            self._context_label.setText(ctx.process_name)
        else:
            self._context_label.setText("")

        # Last Voice Rule
        if state.voice.last_rule:
            self._rule_label.setText("[{0}]".format(state.voice.last_rule))
        else:
            self._rule_label.setText("")
