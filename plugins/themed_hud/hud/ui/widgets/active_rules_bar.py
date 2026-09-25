"""
Dynamic Active Rules Tag Strip Widget.
Renders currently active grammar rules as lightweight badges with sleep state awareness.
Compatible with Python 2.7 and Python 3.x.
"""

from castervoice.lib.qt import QtWidgets, QtGui, QtCore


class ActiveRulesBarWidget(QtWidgets.QWidget):
    """
    Horizontal tag bar displaying active contextual application rules, Global Context,
    or Microphone Sleeping status.
    """

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.setFixedHeight(22)
        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(4, 1, 4, 1)
        self._layout.setSpacing(4)
        self.setLayout(self._layout)
        self._current_rules = ()
        self._current_mic_state = "active"
        self._build_default_view()

    def _build_default_view(self):
        """Renders initial or default global context state."""
        self._clear_layout()
        lbl = QtWidgets.QLabel("<b>Active:</b>")
        lbl.setStyleSheet("color: #60a5fa; font-size: 7.5pt;")
        self._layout.addWidget(lbl)

        default_pill = QtWidgets.QLabel("[Global Context]")
        default_pill.setStyleSheet(
            "background-color: rgba(255, 255, 255, 0.08); color: #94a3b8; "
            "font-size: 7.5pt; border-radius: 2px; padding: 1px 5px; "
            "border: 1px solid rgba(255, 255, 255, 0.12);"
        )
        self._layout.addWidget(default_pill)
        self._layout.addStretch()

    def _clear_layout(self):
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def update_rules(self, rules, mic_state="active"):
        """
        Re-populates rule tag pills if active contextual rule set or mic state changed.
        Suppresses application rule pills when the microphone is sleeping.
        """
        rule_tuple = tuple(rules) if rules else ()
        state_clean = str(mic_state).lower().strip() if mic_state else "active"

        # Memoization: avoid widget rebuild if nothing changed
        if rule_tuple == self._current_rules and state_clean == self._current_mic_state and self._layout.count() > 0:
            return

        self._current_rules = rule_tuple
        self._current_mic_state = state_clean

        self._clear_layout()

        lbl = QtWidgets.QLabel("<b>Active:</b>")
        lbl.setStyleSheet("color: #60a5fa; font-size: 7.5pt;")
        self._layout.addWidget(lbl)

        # 1. Global Context fallback when no active application rules match
        if not rule_tuple:
            default_pill = QtWidgets.QLabel("[Global Context]")
            default_pill.setStyleSheet(
                "background-color: rgba(255, 255, 255, 0.08); color: #94a3b8; "
                "font-size: 7.5pt; border-radius: 2px; padding: 1px 5px; "
                "border: 1px solid rgba(255, 255, 255, 0.12);"
            )
            self._layout.addWidget(default_pill)
        else:
            # 2. Display up to 5 rules cleanly with overflow counter
            max_display = 5
            display_rules = rule_tuple[:max_display]
            for rule in display_rules:
                clean_name = str(rule).strip()
                pill = QtWidgets.QLabel(clean_name)
                pill.setStyleSheet(
                    "background-color: rgba(96, 165, 250, 0.18); color: #93c5fd; "
                    "font-size: 7.5pt; font-weight: bold; border-radius: 2px; "
                    "padding: 1px 5px; border: 1px solid rgba(96, 165, 250, 0.35);"
                )
                self._layout.addWidget(pill)

            if len(rule_tuple) > max_display:
                extra = len(rule_tuple) - max_display
                more_pill = QtWidgets.QLabel("+{0} more".format(extra))
                more_pill.setStyleSheet("color: #64748b; font-size: 7pt;")
                self._layout.addWidget(more_pill)

        self._layout.addStretch()
