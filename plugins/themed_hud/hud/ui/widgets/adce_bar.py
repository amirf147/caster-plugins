"""
ADCE Dynamic Context Strip Widget.
Renders real-time semantic zone ({IntegratedTerminal}, {EditorCodeBuffer}), active IDE tab,
and application process tags when enabled.
Compatible with Python 2.7 and Python 3.x.
"""

from castervoice.lib.qt import QtWidgets, QtGui, QtCore


class AdceBarWidget(QtWidgets.QWidget):
    """
    Modular ADCE dynamic context strip displaying real-time sub-window zone telemetry.
    Renders cleanly when offline or connected.
    """

    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.setFixedHeight(22)
        self._layout = QtWidgets.QHBoxLayout()
        self._layout.setContentsMargins(4, 1, 4, 1)
        self._layout.setSpacing(6)
        self.setLayout(self._layout)

        self._process_name = ""
        self._window_title = ""
        self._semantic_zone = ""
        self._active_file = ""
        self._is_connected = False

        self._build_default_view()

    def _clear_layout(self):
        while self._layout.count() > 0:
            item = self._layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _build_default_view(self):
        """Renders initial or disconnected ADCE state."""
        self._clear_layout()

        # ADCE Indicator Pill (Muted / Offline)
        adce_badge = QtWidgets.QLabel("ADCE")
        adce_badge.setStyleSheet(
            "background-color: rgba(148, 163, 184, 0.15); color: #94a3b8; "
            "font-size: 7.5pt; font-weight: bold; border-radius: 2px; "
            "padding: 1px 5px; border: 1px solid rgba(148, 163, 184, 0.3);"
        )
        self._layout.addWidget(adce_badge)

        status_lbl = QtWidgets.QLabel("[ADCE is not connected]")
        status_lbl.setStyleSheet(
            "background-color: rgba(255, 255, 255, 0.05); color: #64748b; "
            "font-size: 7.5pt; border-radius: 2px; padding: 1px 5px;"
        )
        self._layout.addWidget(status_lbl)
        self._layout.addStretch()

    def update_context(self, process_name="", window_title="", semantic_zone="", active_file="", is_connected=False):
        """
        Updates the ADCE strip view with live semantic telemetry or offline indicator.
        """
        self._is_connected = bool(is_connected)

        if not self._is_connected:
            self._process_name = ""
            self._window_title = ""
            self._semantic_zone = ""
            self._active_file = ""
            self._build_default_view()
            return

        self._process_name = str(process_name or "")
        self._window_title = str(window_title or "")
        self._semantic_zone = str(semantic_zone or "")
        self._active_file = str(active_file or "")

        self._clear_layout()

        # 1. ADCE Status Badge (Green / Active)
        adce_badge = QtWidgets.QLabel("ADCE")
        adce_badge.setStyleSheet(
            "background-color: rgba(34, 197, 94, 0.2); color: #4ade80; "
            "font-size: 7.5pt; font-weight: bold; border-radius: 2px; "
            "padding: 1px 5px; border: 1px solid rgba(34, 197, 94, 0.4);"
        )
        self._layout.addWidget(adce_badge)

        # 2. Semantic Zone Pill ({IntegratedTerminal}, {EditorCodeBuffer}, or {Unknown})
        zone_name = self._semantic_zone if self._semantic_zone else "Unknown"
        zone_pill = QtWidgets.QLabel("{" + zone_name + "}")
        zone_pill.setStyleSheet(
            "background-color: rgba(168, 85, 247, 0.2); color: #c084fc; "
            "font-size: 7.5pt; font-weight: bold; border-radius: 2px; "
            "padding: 1px 5px; border: 1px solid rgba(168, 85, 247, 0.35);"
        )
        self._layout.addWidget(zone_pill)

        # 3. Process / App Pill
        if self._process_name:
            proc_pill = QtWidgets.QLabel("[" + self._process_name + "]")
            proc_pill.setStyleSheet(
                "background-color: rgba(59, 130, 246, 0.15); color: #60a5fa; "
                "font-size: 7.5pt; border-radius: 2px; padding: 1px 5px; "
                "border: 1px solid rgba(59, 130, 246, 0.3);"
            )
            self._layout.addWidget(proc_pill)

        # 4. Active Tab / File Info
        if self._active_file:
            file_display = self._active_file if len(self._active_file) <= 28 else self._active_file[:25] + "..."
            file_pill = QtWidgets.QLabel("📄 " + file_display)
            file_pill.setStyleSheet(
                "background-color: rgba(14, 165, 233, 0.15); color: #38bdf8; "
                "font-size: 7.5pt; border-radius: 2px; padding: 1px 5px; "
                "border: 1px solid rgba(14, 165, 233, 0.25);"
            )
            self._layout.addWidget(file_pill)

        self._layout.addStretch()
