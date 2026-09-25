"""
Typed Event Definitions for HUD Telemetry and Reactive State Mutations.
Compatible with Python 2.7 and Python 3.x.
"""

import time


class HudEvent(object):
    """Base class for all HUD telemetry and command events."""
    event_type = "base"

    def __init__(self, timestamp=None):
        self.timestamp = time.time() if timestamp is None else float(timestamp)

    def to_dict(self):
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
        }


class MicStateEvent(HudEvent):
    """Fired when microphone state transitions between 'on', 'sleeping', and 'off'."""
    event_type = "mic_state"

    def __init__(self, mode="on", timestamp=None):
        HudEvent.__init__(self, timestamp)
        self.mode = str(mode)

    def to_dict(self):
        d = HudEvent.to_dict(self)
        d["mode"] = self.mode
        return d


class RecognitionEvent(HudEvent):
    """Fired when speech recognition completes or fails."""
    event_type = "recognition"

    def __init__(self, phrase="", rule_name="", kind="cmd", duration_ms=0.0, timestamp=None):
        HudEvent.__init__(self, timestamp)
        self.phrase = str(phrase)
        self.rule_name = str(rule_name)
        self.kind = str(kind)
        self.duration_ms = float(duration_ms)

    def to_dict(self):
        d = HudEvent.to_dict(self)
        d["phrase"] = self.phrase
        d["rule_name"] = self.rule_name
        d["kind"] = self.kind
        d["duration_ms"] = self.duration_ms
        return d


class ActiveRulesEvent(HudEvent):
    """Fired when active grammar rules are re-evaluated or updated."""
    event_type = "active_rules"

    def __init__(self, rules=None, timestamp=None):
        HudEvent.__init__(self, timestamp)
        self.rules = list(rules) if rules is not None else []

    def to_dict(self):
        d = HudEvent.to_dict(self)
        d["rules"] = self.rules
        return d


class DesktopContextEvent(HudEvent):
    """Fired when foreground process, title, semantic zone, or ADCE connection state changes."""
    event_type = "desktop_context"

    def __init__(self, process_name="", window_title="", semantic_zone="", active_file="", is_connected=False, timestamp=None):
        HudEvent.__init__(self, timestamp)
        self.process_name = str(process_name)
        self.window_title = str(window_title)
        self.semantic_zone = str(semantic_zone)
        self.active_file = str(active_file)
        self.is_connected = bool(is_connected)

    def to_dict(self):
        d = HudEvent.to_dict(self)
        d["process_name"] = self.process_name
        d["window_title"] = self.window_title
        d["semantic_zone"] = self.semantic_zone
        d["active_file"] = self.active_file
        d["is_connected"] = self.is_connected
        return d


class WindowFocusEvent(HudEvent):
    """Fired when HUD window gains or loses keyboard focus."""
    event_type = "window_focus"

    def __init__(self, is_focused=False, timestamp=None):
        HudEvent.__init__(self, timestamp)
        self.is_focused = bool(is_focused)

    def to_dict(self):
        d = HudEvent.to_dict(self)
        d["is_focused"] = self.is_focused
        return d


class DragModeEvent(HudEvent):
    """Fired when whole-window drag mode is toggled ('D' hotkey)."""
    event_type = "drag_mode"

    def __init__(self, is_drag_mode=False, timestamp=None):
        HudEvent.__init__(self, timestamp)
        self.is_drag_mode = bool(is_drag_mode)

    def to_dict(self):
        d = HudEvent.to_dict(self)
        d["is_drag_mode"] = self.is_drag_mode
        return d


class ThemeChangeEvent(HudEvent):
    """Fired when HUD theme is changed or cycled."""
    event_type = "theme_change"

    def __init__(self, theme_name="classic", timestamp=None):
        HudEvent.__init__(self, timestamp)
        self.theme_name = str(theme_name)

    def to_dict(self):
        d = HudEvent.to_dict(self)
        d["theme_name"] = self.theme_name
        return d


class OpacityChangeEvent(HudEvent):
    """Fired when HUD window, background, or text (letter) opacity is adjusted."""
    event_type = "opacity_change"

    def __init__(self, opacity=1.0, background_opacity=None, text_opacity=None, timestamp=None):
        HudEvent.__init__(self, timestamp)
        self.opacity = float(opacity)
        self.background_opacity = float(background_opacity) if background_opacity is not None else None
        self.text_opacity = float(text_opacity) if text_opacity is not None else None

    def to_dict(self):
        d = HudEvent.to_dict(self)
        d["opacity"] = self.opacity
        if self.background_opacity is not None:
            d["background_opacity"] = self.background_opacity
        if self.text_opacity is not None:
            d["text_opacity"] = self.text_opacity
        return d


class TextAlignmentChangeEvent(HudEvent):
    """Fired when HUD text alignment ('left' or 'right') is adjusted."""
    event_type = "text_alignment_change"

    def __init__(self, text_alignment="left", timestamp=None):
        HudEvent.__init__(self, timestamp)
        self.text_alignment = "right" if str(text_alignment).lower() == "right" else "left"

    def to_dict(self):
        d = HudEvent.to_dict(self)
        d["text_alignment"] = self.text_alignment
        return d


class ClearHistoryEvent(HudEvent):
    """Fired to clear on-screen telemetry log."""
    event_type = "clear_history"


class HeartbeatEvent(HudEvent):
    """Periodic keepalive event from speech engine / Caster daemon."""
    event_type = "heartbeat"

    def __init__(self, engine_name="", timestamp=None):
        HudEvent.__init__(self, timestamp)
        self.engine_name = str(engine_name)

    def to_dict(self):
        d = HudEvent.to_dict(self)
        d["engine_name"] = self.engine_name
        return d


EVENT_TYPE_MAP = {
    "mic_state": lambda d: MicStateEvent(mode=d.get("mode", "on"), timestamp=d.get("timestamp")),
    "recognition": lambda d: RecognitionEvent(
        phrase=d.get("phrase", ""),
        rule_name=d.get("rule_name", ""),
        kind=d.get("kind", "cmd"),
        duration_ms=d.get("duration_ms", 0.0),
        timestamp=d.get("timestamp"),
    ),
    "active_rules": lambda d: ActiveRulesEvent(rules=d.get("rules", []), timestamp=d.get("timestamp")),
    "desktop_context": lambda d: DesktopContextEvent(
        process_name=d.get("process_name", ""),
        window_title=d.get("window_title", ""),
        semantic_zone=d.get("semantic_zone", ""),
        active_file=d.get("active_file", ""),
        is_connected=d.get("is_connected", False),
        timestamp=d.get("timestamp"),
    ),
    "window_focus": lambda d: WindowFocusEvent(is_focused=d.get("is_focused", False), timestamp=d.get("timestamp")),
    "drag_mode": lambda d: DragModeEvent(is_drag_mode=d.get("is_drag_mode", False), timestamp=d.get("timestamp")),
    "theme_change": lambda d: ThemeChangeEvent(theme_name=d.get("theme_name", "classic"), timestamp=d.get("timestamp")),
    "opacity_change": lambda d: OpacityChangeEvent(
        opacity=d.get("opacity", 1.0),
        background_opacity=d.get("background_opacity"),
        text_opacity=d.get("text_opacity"),
        timestamp=d.get("timestamp"),
    ),
    "text_alignment_change": lambda d: TextAlignmentChangeEvent(
        text_alignment=d.get("text_alignment", "left"),
        timestamp=d.get("timestamp"),
    ),
    "clear_history": lambda d: ClearHistoryEvent(timestamp=d.get("timestamp")),
    "heartbeat": lambda d: HeartbeatEvent(engine_name=d.get("engine_name", ""), timestamp=d.get("timestamp")),
}


def event_from_dict(data):
    """Deserialize a JSON dictionary into a strongly-typed HudEvent."""
    if not isinstance(data, dict):
        return HudEvent()
    
    event_type = data.get("event_type", "base")
    factory = EVENT_TYPE_MAP.get(event_type)
    if factory:
        return factory(data)
    return HudEvent(timestamp=data.get("timestamp"))
