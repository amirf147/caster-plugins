<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright (c) 2026 Amir Farhadi -->

# Dynamic Cursor Plugin

[![Companion Daemon](https://img.shields.io/badge/Companion%20Daemon-dynamic--cursor-blueviolet.svg)](https://github.com/amirf147/dynamic-cursor)

Named Pipe bridge projecting real-time Caster microphone states and Active Desktop Context Engine (ADCE) semantic focus zones onto the Windows hardware cursor.

---

## Architecture Overview

The `dynamic_cursor` plugin integrates Caster engine state transitions with the standalone [dynamic-cursor](https://github.com/amirf147/dynamic-cursor) daemon. It subscribes in-process to `EngineModesManager` and `adce.add_context_listener`, dispatching two orthogonal visual layers across a low-latency Win32 Named Pipe (`\\.\pipe\dynamic_cursor`):

1. **Microphone Layer (`layer_id="caster_mic"`, `priority=80`)**: Tints the hardware cursor body green when awake, red when sleeping, and gray with a muted badge when off.
2. **Context Layer (`layer_id="adce_context"`, `priority=30`)**: Stamps bottom-right corner badges indicating semantic focus (`web_globe`, `code_brackets`, `terminal_prompt`, `doc_writing`).

```
[ Caster Engine Modes ] ---> [ dynamic_cursor plugin ] ---> \\.\pipe\dynamic_cursor ---> [ dynamic-cursor daemon ]
             +                          |                                                          |
[ ADCE Focus Context ] -----------------+                                                - Procedural 16x16 Badges
                                                                                         - SetSystemCursor Swapping
```

---

## Features

- **Decoupled Operation**: Pushes visual layers over length-prefixed JSON frames without embedding domain logic into the native compositor.
- **State Deduplication**: Suppresses redundant frame transmissions when microphone modes or focus zones remain unchanged.
- **Automatic Reconnection & Replay**: Caches active layers and automatically replays state if the daemon restarts.
- **Event-Driven Foreground Fallback**: When ADCE is disconnected, listens to Win32 `EVENT_SYSTEM_FOREGROUND` transitions via a dedicated message pump.

---

## Installation & Companion Daemon

### 1. Install Companion Daemon
Clone, build, or download `dynamic-cursor-tray.exe` from the companion repository:
[**dynamic-cursor**](https://github.com/amirf147/dynamic-cursor)

Ensure `dynamic-cursor-tray.exe` is placed on the system `PATH` or located in `~/Documents/repos/dynamic-cursor/build/Release/dynamic-cursor-tray.exe`. Alternatively, configure the `DYNAMIC_CURSOR_EXE` environment variable directly to the binary location.

### 2. Install Caster Plugin
Install using the Caster plugin CLI:

```powershell
py -3.10 -m castervoice.bin.plugin_cli install dynamic_cursor
```

The plugin installs into `%LOCALAPPDATA%\caster\caster_user_content\plugins\dynamic_cursor\` and activates automatically on next Caster startup.

---

## Configuration (`settings.toml`)

Options are managed automatically via the Caster Plugin Manager GUI or defined manually in `%LOCALAPPDATA%\caster\settings.toml`:

```toml
[plugins.dynamic_cursor]
enabled = true
pipe_name = "dynamic_cursor"
autostart_daemon = true
enable_mic_tint = true
enable_context_badges = true
listening_tint = "#44FF66"
sleeping_tint = "#FF5555"
muted_tint = "#888888"
```

### Parameter Reference

| Parameter | Type | Default | Description |
|---|---|---|---|
| `pipe_name` | string | `"dynamic_cursor"` | Named Pipe endpoint name (`\\.\pipe\<name>`). |
| `autostart_daemon` | bool | `true` | Launches `dynamic-cursor-tray.exe` automatically if the pipe is inactive. |
| `enable_mic_tint` | bool | `true` | Controls pointer body tinting according to mic state. |
| `enable_context_badges` | bool | `true` | Controls bottom-right procedural corner badges. |
| `listening_tint` | string | `"#44FF66"` | Hex color tint when Caster microphone is awake. |
| `sleeping_tint` | string | `"#FF5555"` | Hex color tint when Caster microphone is sleeping. |
| `muted_tint` | string | `"#888888"` | Hex color tint when Caster microphone is off. |

---

## IPC Framing Contract

Frames dispatched to `\\.\pipe\dynamic_cursor` use a 4-byte little-endian length prefix followed by UTF-8 encoded JSON:

```
[ Length: 4 bytes uint32_le ] [ JSON UTF-8 Payload ]
```

### Example Microphone Upsert
```json
{
  "op": "upsert",
  "layer_id": "caster_mic",
  "priority": 80,
  "tint_rgba": "#44FF66"
}
```

### Example Context Badge Upsert
```json
{
  "op": "upsert",
  "layer_id": "adce_context",
  "priority": 30,
  "badge_id": "terminal_prompt"
}
```
