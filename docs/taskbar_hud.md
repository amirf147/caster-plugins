# Taskbar HUD Plugin Guide

The `taskbar_hud` plugin bridges Caster recognition telemetry and active context rules directly into the Windows 11 Taskbar via a local Windows Named Pipe (`\\.\pipe\CasterTaskbarHud`). It communicates with the `caster-taskbar-hud` Windhawk mod running inside `explorer.exe`.

---

## 1. Compatibility & Prerequisites

| Requirement | Specification |
|---|---|
| **Operating System** | Windows 11 (64-bit) |
| **Caster Version** | >= 1.7.0 |
| **Companion Mod** | Windhawk + `caster-taskbar-hud` mod active in Windhawk |
| **IPC Mechanism** | Windows Named Pipe (`\\.\pipe\CasterTaskbarHud`) |

---

## 2. CLI Management

Use the Caster plugin CLI from any terminal prompt:

### Install
```powershell
py -3.10 -m castervoice.bin.plugin_cli install taskbar_hud
```

### Update
```powershell
py -3.10 -m castervoice.bin.plugin_cli update taskbar_hud
```

### Enable
```powershell
py -3.10 -m castervoice.bin.plugin_cli enable taskbar_hud
```

### Disable
```powershell
py -3.10 -m castervoice.bin.plugin_cli disable taskbar_hud
```

### Check Status
```powershell
py -3.10 -m castervoice.bin.plugin_cli list
```

---

## 3. Configuration (`settings.toml`)

Configuration is stored in `%LOCALAPPDATA%\caster\settings.toml`. The `[plugins.taskbar_hud]` section controls bridge behavior:

```toml
[plugins.taskbar_hud]
enabled = true
pipe_name = "CasterTaskbarHud"
```

### Parameter Reference

* `enabled` (boolean, default: `true`): Whether Caster initializes the Named Pipe client and dispatches speech events on startup.
* `pipe_name` (string, default: `"CasterTaskbarHud"`): Name of the Named Pipe endpoint created by the Windhawk mod.

---

## 4. How It Operates

1. **Named Pipe Bridge**:
   - On startup, the plugin connects to `\\.\pipe\CasterTaskbarHud`.
   - If Windhawk or the mod is not running, the client queues reconnection attempts without blocking or stalling speech recognition.

2. **Telemetry Streaming**:
   - **Microphone State**: Real-time updates when mic toggles (`on`, `sleeping`, `off`).
   - **Speech Recognition**: Displays recognized grammar phrases and live status in the taskbar widget.
   - **Context Resolution**: When `adce` is loaded, it displays semantic sub-window zones. When `adce` is disabled, a built-in background watcher tracks active Win32 foreground windows and updates active voice rules.

3. **Enabling and Disabling**:
   - Setting `enabled = false` completely disables Named Pipe connection attempts and unregisters the print/mic handlers.
   - Setting `enabled = true` re-enables live telemetry streaming on the next Caster startup.

---

## 5. Verification & Troubleshooting

1. Ensure the Windhawk mod is compiled and loaded in Windhawk on Windows 11.
2. Start Caster with `taskbar_hud` enabled.
3. Check the Windows Taskbar for the HUD display showing the current microphone status and active grammar rules.
