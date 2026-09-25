"""
Telemetry Log Widget for Continuous Speech Recognition History.
Optimized for ultra-compact heights (25px-40px) with descender-safe typography and auto-scroll.
Compatible with Python 2.7 and Python 3.x.
"""

from castervoice.lib.qt import QtWidgets, QtGui, QtCore, qt_attr
from hud.core.state import LogEntry

TEXT_CURSOR_END = qt_attr(
    QtGui,
    ("QTextCursor", "End"),
    ("QTextCursor", "MoveOperation", "End"),
)


class TelemetryLogWidget(QtWidgets.QTextEdit):
    """
    High-performance telemetry log stream widget.
    Renders formatted command history, handles paint coalescing, and auto-scrolls to the newest entry.
    """

    def __init__(self, parent=None):
        QtWidgets.QTextEdit.__init__(self, parent)
        self.setReadOnly(True)
        self.setMinimumSize(0, 0)
        self.setFrameStyle(0)
        self.document().setDocumentMargin(2)
        self.viewport().setMouseTracking(True)

        click_focus = qt_attr(QtCore, ("Qt", "ClickFocus"), ("Qt", "FocusPolicy", "ClickFocus"))
        self.setFocusPolicy(click_focus)

        ignored_policy = qt_attr(
            QtWidgets,
            ("QSizePolicy", "Ignored"),
            ("QSizePolicy", "Policy", "Ignored"),
        )
        self.setSizePolicy(ignored_policy, ignored_policy)
        self._custom_border_css = ""
        self._current_theme = "classic"
        self._text_alignment = "left"
        self._entry_count = 0

    def set_text_alignment(self, alignment):
        """Sets text alignment ('left' or 'right') dynamically across all blocks."""
        align_str = "right" if str(alignment).lower() == "right" else "left"
        self._text_alignment = align_str
        align_flag = (
            qt_attr(QtCore, ("Qt", "AlignRight"), ("Qt", "AlignmentFlag", "AlignRight"))
            if align_str == "right"
            else qt_attr(QtCore, ("Qt", "AlignLeft"), ("Qt", "AlignmentFlag", "AlignLeft"))
        )

        cursor = QtGui.QTextCursor(self.document())
        cursor.select(QtGui.QTextCursor.Document)
        bf = QtGui.QTextBlockFormat()
        bf.setAlignment(align_flag)
        cursor.mergeBlockFormat(bf)

        opt = self.document().defaultTextOption()
        opt.setAlignment(align_flag)
        self.document().setDefaultTextOption(opt)
        self.scroll_to_end()

    def _append_formatted(self, html_snippet):
        """Appends formatted HTML entry ensuring paragraph alignment is applied."""
        align_flag = (
            qt_attr(QtCore, ("Qt", "AlignRight"), ("Qt", "AlignmentFlag", "AlignRight"))
            if getattr(self, "_text_alignment", "left") == "right"
            else qt_attr(QtCore, ("Qt", "AlignLeft"), ("Qt", "AlignmentFlag", "AlignLeft"))
        )
        html_to_insert = '<div align="{0}">{1}</div>'.format(self._text_alignment, html_snippet)
        if self.document().isEmpty():
            self.setHtml(html_to_insert)
        else:
            self.append(html_to_insert)
        self.setAlignment(align_flag)

    def set_border_style(self, border_css):
        """Updates border style dynamically."""
        self._custom_border_css = border_css
        # Preserve background and text color by setting border properties
        self.setStyleSheet("QTextEdit {{ {0} }}".format(border_css))

    def update_history(self, history, theme_name="classic"):
        """Re-renders history buffer or appends new items."""
        self._current_theme = theme_name
        self.clear()
        for entry in history:
            self._append_formatted(entry.formatted_html(theme_name))
        self.scroll_to_end()

    def append_entry(self, entry, theme_name="classic"):
        """Appends a single new entry and scrolls to bottom."""
        self._current_theme = theme_name
        formatted = entry.formatted_html(theme_name)
        self._append_formatted(formatted)
        self._entry_count = (self._entry_count + 1) % 50
        self.scroll_to_end()

    def append_system_text(self, text, theme_name="classic"):
        """Helper to append system/informational messages."""
        entry = LogEntry(text=text, kind="sys")
        self._append_formatted(entry.formatted_html(theme_name))
        self.scroll_to_end()

    def scroll_to_end(self):
        """Moves text cursor to the end to guarantee visibility of newest commands."""
        cursor = self.textCursor()
        cursor.movePosition(TEXT_CURSOR_END)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def apply_scrollbar_policy(self, hide_scrollbars):
        """Toggles scrollbars on/off with immediate viewport and layout refresh."""
        policy = qt_attr(
            QtCore,
            ("Qt", "ScrollBarAlwaysOff" if hide_scrollbars else "ScrollBarAsNeeded"),
            ("Qt", "ScrollBarPolicy", "ScrollBarAlwaysOff" if hide_scrollbars else "ScrollBarAsNeeded"),
        )
        self.setVerticalScrollBarPolicy(policy)
        self.setHorizontalScrollBarPolicy(policy)
        self.updateGeometry()
        self.viewport().update()

    def contextMenuEvent(self, event):
        """Override default QTextEdit context menu to show full Caster HUD menu."""
        parent = self.parent()
        while parent and not isinstance(parent, QtWidgets.QMainWindow):
            parent = parent.parent()
        if parent and hasattr(parent, "show_context_menu"):
            parent.show_context_menu(event.pos())
            event.accept()
        else:
            QtWidgets.QTextEdit.contextMenuEvent(self, event)

    def keyPressEvent(self, event):
        """Forward hotkeys to parent main window."""
        parent = self.parent()
        while parent and not isinstance(parent, QtWidgets.QMainWindow):
            parent = parent.parent()
        if parent:
            if parent.handle_key(event):
                event.accept()
                return
        QtWidgets.QTextEdit.keyPressEvent(self, event)
