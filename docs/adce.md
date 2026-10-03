# ADCE (Active Desktop Context Engine) Plugin Guide

The `adce` plugin connects Caster to the out-of-process Active Desktop Context Engine via Server-Sent Events (SSE). It streams real-time UI Automation focus transitions, sub-window semantic zones (e.g., active terminal vs. editor panel in VS Code), and focused file paths into Caster's context resolution pipeline.

---

## 1. Compatibility & Prerequisites

| Requirement | Specification |
|---|---|
| **Operating System** | Windows 10 / Windows 11 (64-bit) |
| **Caster Version** | >= 1.7.0 |
| **External Service** | ADCE Daemon (built with .NET 8/9 SDK or compiled binary) |
| **Default Port** | `127.0.0.1:8424` (HTTP / SSE) |

---

## 2. CLI Management

Use the Caster plugin CLI from any terminal prompt:

### Install
```powershell
py -3.10 -m castervoice.bin.plugin_cli install adce
```

### Update
```powershell
py -3.10 -m castervoice.bin.plugin_cli update adce
```

### Enable
```powershell
py -3.10 -m castervoice.bin.plugin_cli enable adce
```

### Disable
```powershell
py -3.10 -m castervoice.bin.plugin_cli disable adce
```

### Check Status
```powershell
py -3.10 -m castervoice.bin.plugin_cli list
```

---

## 3. Configuration (`settings.toml`)

Configuration is stored in `%LOCALAPPDATA%\caster\settings.toml`. When enabled, the `[plugins.adce]` section controls connection and auto-spawning behavior:

```toml
[plugins.adce]
enabled = true
host = "127.0.0.1"
port = 8424
autostart = true
startup_command = "dotnet run --project src/ADCE.Daemon"
startup_cwd = ""
```

### Parameter Reference

* `enabled` (boolean, default: `true`): Whether Caster loads and starts the ADCE bridge on startup.
* `host` (string, default: `"127.0.0.1"`): Host address where the ADCE daemon listens.
* `port` (integer, default: `8424`): Port number for the HTTP / SSE endpoint.
* `autostart` (boolean, default: `true`): When `true`, if Caster detects that the daemon is not running on startup, it automatically spawns the background process.
* `startup_command` (string, optional): Custom command to launch the ADCE daemon if not using the default dotnet run.
* `startup_cwd` (string, optional): Working directory from which to execute `startup_command`.

---

## 4. How Enabling and Disabling Works

1. **When `enabled = false`**:
   - On Caster startup, the plugin loader ignores `adce`.
   - No background SSE connection is established, and no background daemon is auto-spawned.
   - Other plugins (such as `taskbar_hud` or `themed_hud`) fall back to standard Win32 foreground window polling.

2. **When re-enabling (`enabled = true` or `plugin_cli enable adce`)**:
   - The CLI or configuration file sets `enabled = true` in `settings.toml`.
   - On the next Caster startup, `AdcePlugin` initializes, checks for the daemon on `127.0.0.1:8424`, spawns it if `autostart = true`, and connects to the SSE event stream.
   - When Caster exits, any daemon process spawned by Caster is automatically terminated via process tree cleanup.

---

## 5. Verification

To verify that ADCE is actively streaming context:

1. Launch Caster with `adce` enabled.
2. Observe console logs or status in HUD:
   ```text
   [ADCE] Connected to SSE context stream at http://127.0.0.1:8424/events
   ```
3. Switching focus between an editor pane and an integrated terminal will emit sub-window context transitions into Caster rules.
