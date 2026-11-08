<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- Copyright (c) 2026 Amir Farhadi -->

# Dynamic Cursor Plugin Guide

The `dynamic_cursor` plugin bridges Caster microphone states and Active Desktop Context Engine (ADCE) semantic focus zones onto the Windows hardware cursor via a local Windows Named Pipe (`\\.\pipe\dynamic_cursor`). It communicates with the standalone [dynamic-cursor](https://github.com/amirf147/dynamic-cursor) companion daemon.

---

## 1. Compatibility & Prerequisites

| Requirement | Specification |
|---|---|
| **Operating System** | Windows 10/11 (64-bit) |
| **Caster Version** | >= 1.7.0 |
| **Companion Daemon** | [dynamic-cursor](https://github.com/amirf147/dynamic-cursor) (`dynamic-cursor-tray.exe` running or discoverable in path) |
| **IPC Mechanism** | Windows Named Pipe (`\\.\pipe\dynamic_cursor`) |

---

## 2. CLI Management

Manage the plugin using the standard Caster plugin CLI:

### Install
```powershell
py -3.10 -m castervoice.bin.plugin_cli install dynamic_cursor
```

### Update
```powershell
py -3.10 -m castervoice.bin.plugin_cli update dynamic_cursor
```

### Enable
```powershell
py -3.10 -m castervoice.bin.plugin_cli enable dynamic_cursor
```

### Disable
```powershell
py -3.10 -m castervoice.bin.plugin_cli disable dynamic_cursor
```

### Check Status
```powershell
py -3.10 -m castervoice.bin.plugin_cli list
```

---

## 3. Configuration (`settings.toml`)

Configuration is stored in `%LOCALAPPDATA%\caster\settings.toml`. The `[plugins.dynamic_cursor]` section controls bridge behavior:

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

* `enabled` (boolean, default: `true`): Whether Caster initializes the Named Pipe client on startup.
* `pipe_name` (string, default: `"dynamic_cursor"`): Endpoint name for the Win32 Named Pipe.
* `autostart_daemon` (boolean, default: `true`): Automatically starts `dynamic-cursor-tray.exe` if not active.
* `enable_mic_tint` (boolean, default: `true`): Applies cursor body color tinting according to mic state.
* `enable_context_badges` (boolean, default: `true`): Stamped corner badge based on active semantic zone.
* `listening_tint` (string, default: `"#44FF66"`): Hex color tint for active microphone mode.
* `sleeping_tint` (string, default: `"#FF5555"`): Hex color tint for sleeping microphone mode.
* `muted_tint` (string, default: `"#888888"`): Hex color tint for muted or turned off microphone mode.

---

## 4. How It Operates

1. **Named Pipe Bridge**:
   On initialization, the plugin connects to `\\.\pipe\dynamic_cursor`. If the daemon is not running and `autostart_daemon` is enabled, the plugin attempts to spawn `dynamic-cursor-tray.exe` detached.

2. **Orthogonal Layer Model**:
   State transitions are split into two independent layers with different priorities:
   - Microphone State (`layer_id="caster_mic"`, `priority=80`): Tints the pointer arrow body.
   - Focus Context (`layer_id="adce_context"`, `priority=30`): Stamps bottom-right corner badges.

3. **Sub-Window Context Resolution**:
   When ADCE is active, incoming focus events provide fine-grained sub-window zones. Terminal buffers receive `terminal_prompt`, browser documents receive `web_globe`, and editor buffers receive `code_brackets`.

4. **Event-Driven Win32 Foreground Hook**:
   If ADCE is not active, the plugin registers a native Win32 `SetWinEventHook` listening for `EVENT_SYSTEM_FOREGROUND`. Transitions are processed through a 40 ms trailing-edge debouncer, avoiding polling loops.

5. **Clean Restoration on Teardown**:
   When Caster exits or the plugin is disabled, `stop()` issues a `clear` operation to restore the default Windows cursor scheme before closing IPC handles.

---

## 5. Verification & Troubleshooting

1. Ensure the companion daemon is built or installed from [dynamic-cursor](https://github.com/amirf147/dynamic-cursor).
2. Start Caster with `dynamic_cursor` enabled.
3. Verify pointer color tinting reflects microphone transitions (`awake`, `sleeping`, `off`) and contextual badges match active application zones.
