# Taskbar HUD Plugin

[![Companion Mod](https://img.shields.io/badge/Windhawk%20Mod-caster--taskbar--hud-blueviolet.svg)](https://github.com/amirf147/caster-taskbar-hud)

Named Pipe bridge projecting real-time Caster voice recognition telemetry and Active Desktop Context Engine (ADCE) focus states directly into the Windows 11 Taskbar.

![Taskbar HUD & ADCE Live Telemetry](../../docs/media/taskbar_hud_adce_demo.gif)

---

## Architecture Overview

This plugin intercepts Caster engine events, resolves active contextual grammar rules via dynamic AST inspection, and streams lightweight JSON telemetry packets over a low-latency Win32 Named Pipe (`\\.\pipe\CasterTaskbarHud`) to the native [Caster Taskbar HUD Windhawk Mod](https://github.com/amirf147/caster-taskbar-hud).

```
[ Caster Engine ] ---> [ taskbar_hud plugin ] ---> \\.\pipe\CasterTaskbarHud ---> [ Windhawk Mod in Explorer ]
                             |                                                               |
                     - Context Resolver                                              - WinRT XAML Elements
                     - ADCE Zone Tracker                                             - SystemTrayFrameGrid
                     - Mic Mode Listener                                             - Status Dot & Carousel
```

---

## Installation

### 1. Install Caster Plugin
Install using the Caster plugin CLI:

```powershell
py -3.10 -m castervoice.bin.plugin_cli install taskbar_hud
```

The plugin installs into `%LOCALAPPDATA%\caster\caster_user_content\plugins\taskbar_hud\` and activates automatically on next Caster startup.

### 2. Install Windhawk Mod
Follow the installation guide in the companion repository:
👉 [**Caster Taskbar HUD Mod (Windhawk)**](https://github.com/amirf147/caster-taskbar-hud)

---

## IPC Telemetry Payload

Packets dispatched to `\\.\pipe\CasterTaskbarHud` follow this format:

```json
{
  "command": "format document",
  "rules": "Python, VS Code",
  "adce_zone": "Editor",
  "status": "recognized"
}
```

### Status Types:
- `idle`: Microphone awake, waiting for voice input.
- `streaming`: Live speech hypothesis currently being spoken.
- `recognized`: Voice command recognized and executed.
- `sleeping`: Microphone sleeping or muted.
- `error`: Speech recognition error.

---

## Standalone Testing

To test the HUD without Caster running, clone the companion [caster-taskbar-hud](https://github.com/amirf147/caster-taskbar-hud) repository and run its test harness:

```powershell
python scripts/test_taskbar_hud_stream.py
```
