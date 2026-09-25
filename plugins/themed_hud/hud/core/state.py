"""
Reactive State Model for the Caster Heads-Up Display.
Compatible with Python 2.7 and Python 3.x.
"""

import time
import copy
from hud.core import constants

try:
    import html
    html_escape = html.escape
except (ImportError, AttributeError):
    import cgi
    html_escape = cgi.escape


class LogEntry(object):
    """A single entry in the recognition / telemetry history stream."""

    def __init__(self, text, kind="cmd", rule_name="", timestamp=None):
        self.text = str(text)
        self.kind = str(kind)          # "cmd" ($ blue), "sys" (@ purple), "err" (red)
        self.rule_name = str(rule_name)
        self.timestamp = time.time() if timestamp is None else float(timestamp)

    def formatted_html(self, theme_name="classic"):
        """Format entry as HTML with color-coded directional arrow."""
        escaped = html_escape(self.text)
        try:
            from hud.theming.theme_manager import ThemeManager
            colors = ThemeManager.get_theme_colors(theme_name)
        except Exception:
            colors = {}

        if self.kind == "cmd":
            col = colors.get("cmd_color", "blue" if theme_name == "classic" else constants.COLOR_TEXT_CMD)
            return '<font color="{0}">&lt;</font><b>{1}</b>'.format(col, escaped)
        elif self.kind == "sys":
            col = colors.get("sys_color", "purple" if theme_name == "classic" else constants.COLOR_TEXT_SYS)
            return '<font color="{0}">&gt;</font><b>{1}</b>'.format(col, escaped)
        else:
            col = colors.get("err_color", "red" if theme_name == "classic" else constants.COLOR_TEXT_ERR)
            return '<font color="{0}">&gt;</font>{1}'.format(col, escaped)

    def __repr__(self):
        return "LogEntry(text={0!r}, kind={1!r})".format(self.text, self.kind)

    def __eq__(self, other):
        return isinstance(other, LogEntry) and self.text == other.text and self.kind == other.kind


class VoiceState(object):
    """Voice engine telemetry and active rule context."""

    def __init__(self, last_phrase="", last_rule="", active_rules=None, loaded_grammars_count=0):
        self.last_phrase = str(last_phrase)
        self.last_rule = str(last_rule)
        self.active_rules = tuple(active_rules) if active_rules is not None else ()
        self.loaded_grammars_count = int(loaded_grammars_count)

    def clone(self, **kwargs):
        return VoiceState(
            last_phrase=kwargs.get("last_phrase", self.last_phrase),
            last_rule=kwargs.get("last_rule", self.last_rule),
            active_rules=kwargs.get("active_rules", self.active_rules),
            loaded_grammars_count=kwargs.get("loaded_grammars_count", self.loaded_grammars_count),
        )


class DesktopContextState(object):
    """Physical desktop state (from Win32 or optional ADCE engine)."""

    def __init__(self, process_name="", window_title="", semantic_zone="", active_file="", is_connected=False):
        self.process_name = str(process_name)
        self.window_title = str(window_title)
        self.semantic_zone = str(semantic_zone)
        self.active_file = str(active_file)
        self.is_connected = bool(is_connected)


class HudState(object):
    """
    Central, reactive state store for the Caster HUD subsystem.
    """

    def __init__(self, mic_mode="on", is_drag_mode=False, is_focused=False,
                 engine_connected=True, last_heartbeat=None, voice=None,
                 desktop_context=None, history=None, max_history=50,
                 theme="classic", frameless=False, opacity=1.0,
                 background_opacity=None, text_opacity=1.0,
                 text_alignment="left", config=None):
        self.mic_mode = str(mic_mode)
        self.is_drag_mode = bool(is_drag_mode)
        self.is_focused = bool(is_focused)
        self.engine_connected = bool(engine_connected)
        self.last_heartbeat = time.time() if last_heartbeat is None else float(last_heartbeat)

        self.voice = voice if voice is not None else VoiceState()
        self.desktop_context = desktop_context if desktop_context is not None else DesktopContextState()
        self.history = tuple(history) if history is not None else ()
        self.max_history = int(max_history)

        self.theme = str(theme)
        self.frameless = bool(frameless)
        self.opacity = float(opacity)
        self.background_opacity = float(background_opacity if background_opacity is not None else opacity)
        self.text_opacity = float(text_opacity)
        self.text_alignment = "right" if str(text_alignment).lower() == "right" else "left"
        self.config = config if config is not None else constants.merge_hud_config()

    def get_border_color(self):
        """
        Computes border accent color adhering strictly to the Safety Priority Hierarchy:
        Mic State (Red/Green) > Drag Mode (Amber) > Window Focus (Blue).
        """
        if self.mic_mode == "sleeping":
            return constants.COLOR_MIC_SLEEPING   # Pure Red (Safety Priority)
        if self.is_drag_mode:
            return constants.COLOR_DRAG           # Amber (Drag Active)
        if self.is_focused:
            return constants.COLOR_FOCUS          # Accent Blue (Window Selected)
        if self.mic_mode == "on":
            return constants.COLOR_MIC_ON         # Vibrant Green (Listening / Awake)
        return constants.COLOR_BORDER_MINIMAL

    def get_status_text(self):
        """User-friendly status text for badges / pills."""
        if self.mic_mode == "sleeping":
            return "SLEEPING"
        elif self.mic_mode == "on":
            return "LISTENING"
        return "OFFLINE"

    def clone(self, **kwargs):
        """Creates a modified shallow copy of the state."""
        return HudState(
            mic_mode=kwargs.get("mic_mode", self.mic_mode),
            is_drag_mode=kwargs.get("is_drag_mode", self.is_drag_mode),
            is_focused=kwargs.get("is_focused", self.is_focused),
            engine_connected=kwargs.get("engine_connected", self.engine_connected),
            last_heartbeat=kwargs.get("last_heartbeat", self.last_heartbeat),
            voice=kwargs.get("voice", self.voice),
            desktop_context=kwargs.get("desktop_context", self.desktop_context),
            history=kwargs.get("history", self.history),
            max_history=kwargs.get("max_history", self.max_history),
            theme=kwargs.get("theme", self.theme),
            frameless=kwargs.get("frameless", self.frameless),
            opacity=kwargs.get("opacity", self.opacity),
            background_opacity=kwargs.get("background_opacity", self.background_opacity),
            text_opacity=kwargs.get("text_opacity", self.text_opacity),
            text_alignment=kwargs.get("text_alignment", self.text_alignment),
            config=kwargs.get("config", self.config),
        )
