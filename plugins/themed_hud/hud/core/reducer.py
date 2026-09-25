"""
Pure State Reducers for the Caster HUD Subsystem.
Compatible with Python 2.7 and Python 3.x.
"""

from hud.core.state import (
    HudState,
    VoiceState,
    DesktopContextState,
    LogEntry,
)
from hud.core.events import (
    HudEvent,
    MicStateEvent,
    RecognitionEvent,
    ActiveRulesEvent,
    DesktopContextEvent,
    WindowFocusEvent,
    DragModeEvent,
    ThemeChangeEvent,
    OpacityChangeEvent,
    TextAlignmentChangeEvent,
    ClearHistoryEvent,
    HeartbeatEvent,
)


def reduce_event(state, event):
    """
    Pure state reduction function. Given a current HudState and incoming HudEvent,
    computes and returns the next immutable HudState.
    """
    if isinstance(event, MicStateEvent):
        return state.clone(mic_mode=event.mode)

    elif isinstance(event, RecognitionEvent):
        new_entry = LogEntry(
            text=event.phrase,
            kind=event.kind,
            rule_name=event.rule_name,
            timestamp=event.timestamp,
        )
        
        new_history = state.history + (new_entry,)
        if len(new_history) > state.max_history:
            new_history = new_history[-state.max_history:]
            
        new_voice = state.voice.clone(
            last_phrase=event.phrase,
            last_rule=event.rule_name,
        )
        return state.clone(history=new_history, voice=new_voice)

    elif isinstance(event, ActiveRulesEvent):
        new_voice = state.voice.clone(active_rules=tuple(event.rules))
        return state.clone(voice=new_voice)

    elif isinstance(event, DesktopContextEvent):
        new_context = DesktopContextState(
            process_name=event.process_name,
            window_title=event.window_title,
            semantic_zone=event.semantic_zone,
            active_file=event.active_file,
            is_connected=event.is_connected,
        )
        return state.clone(desktop_context=new_context)

    elif isinstance(event, WindowFocusEvent):
        return state.clone(is_focused=event.is_focused)

    elif isinstance(event, DragModeEvent):
        return state.clone(is_drag_mode=event.is_drag_mode)

    elif isinstance(event, ThemeChangeEvent):
        return state.clone(theme=event.theme_name)

    elif isinstance(event, OpacityChangeEvent):
        bg_op = event.background_opacity if event.background_opacity is not None else state.background_opacity
        txt_op = event.text_opacity if event.text_opacity is not None else state.text_opacity
        return state.clone(
            opacity=max(0.1, min(1.0, float(event.opacity))),
            background_opacity=max(0.0, min(1.0, float(bg_op))),
            text_opacity=max(0.1, min(1.0, float(txt_op))),
        )

    elif isinstance(event, TextAlignmentChangeEvent):
        align = "right" if str(event.text_alignment).lower() == "right" else "left"
        return state.clone(text_alignment=align)

    elif isinstance(event, ClearHistoryEvent):
        return state.clone(history=())

    elif isinstance(event, HeartbeatEvent):
        return state.clone(engine_connected=True, last_heartbeat=event.timestamp)

    return state
