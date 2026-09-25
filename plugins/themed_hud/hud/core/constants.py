"""
HUD Constants, Default Layout Dimensions, Colors, and Configuration Fallbacks.
"""

# Default Network Configuration
DEFAULT_HUD_HOST = "127.0.0.1"
DEFAULT_HUD_PORT = 8339         # High-performance async ndjson telemetry stream
DEFAULT_HUD_RPC_PORT = 8338     # Backward-compatible Caster XML-RPC endpoint

# Default Window Geometry
DEFAULT_HUD_WIDTH = 300
DEFAULT_HUD_HEIGHT = 200
COMPACT_HUD_HEIGHT = 36
DEFAULT_HUD_MARGIN = 30
DEFAULT_FONT_SIZE = 9
DEFAULT_FONT_FAMILY = "Segoe UI"

# Visual Status Border & Accent Colors
COLOR_MIC_ON = "#2ecc71"         # Vibrant Green (Listening / Awake)
COLOR_MIC_SLEEPING = "#e74c3c"   # Pure Red (Sleeping / Safety Invariant)
COLOR_FOCUS = "#3498db"          # Accent Blue (Window Focused)
COLOR_DRAG = "#f39c12"           # Amber / Orange (Drag Mode Active)
COLOR_BORDER_MINIMAL = "rgba(255, 255, 255, 0.15)"

# Telemetry Text Colors
COLOR_TEXT_CMD = "#3498db"       # Blue (Recognized Voice Commands)
COLOR_TEXT_SYS = "#9b59b6"       # Purple (System / Mode Information)
COLOR_TEXT_ERR = "#e74c3c"       # Red (Errors / Recognition Failures)

# Resize Hit Margins (Win32 Native DWM & Fallback)
RESIZE_MARGIN_HORIZONTAL = 6     # Left / Right hit margin in pixels
RESIZE_MARGIN_VERTICAL = 3       # Top / Bottom hit margin in pixels (optimized for slim 25px-30px containers)

# Comprehensive TOML Configuration Defaults
DEFAULT_HUD_CONFIG = {
    "system_tray": False,
    "theme": "classic",
    "frameless": False,
    "opacity": 1.0,
    "status_border": True,
    "show_status_bar": False,
    "show_active_rules": False,
    "show_context": False,
    "max_history_lines": 50,
    "font_family": DEFAULT_FONT_FAMILY,
    "font_size": DEFAULT_FONT_SIZE,
    "hide_scrollbars": False,
    "port": DEFAULT_HUD_PORT,
    "host": DEFAULT_HUD_HOST,
}


def merge_hud_config(user_config=None):
    """
    Merge user-supplied settings dictionary with DEFAULT_HUD_CONFIG,
    preventing KeyErrors when upgrading from older settings.toml files.
    """
    config = DEFAULT_HUD_CONFIG.copy()
    if isinstance(user_config, dict):
        for k, v in user_config.items():
            if k in config and v is not None:
                config[k] = v
    return config
