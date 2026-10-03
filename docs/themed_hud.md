# Themed HUD Plugin Guide

The `themed_hud` plugin provides a modular desktop overlay HUD built on Qt (PySide2). It features 10+ built-in QSS color themes, adjustable opacity, interactive drag-and-drop repositioning, telemetry feeds, and ADCE dynamic context strips.

---

## 1. Compatibility & Prerequisites

| Requirement | Specification |
|---|---|
| **Operating System** | Windows 10/11, Linux, macOS |
| **Caster Version** | >= 1.7.0 |
| **Python Dependencies** | `PySide2` (`py -3.10 -m pip install PySide2`) |
| **Replaces Core HUD** | Yes (`replaces_hud = true`) |

---

## 2. CLI Management

Use the Caster plugin CLI from any terminal prompt:

### Install
```powershell
py -3.10 -m castervoice.bin.plugin_cli install themed_hud
```

### Update
```powershell
py -3.10 -m castervoice.bin.plugin_cli update themed_hud
```

### Enable
```powershell
py -3.10 -m castervoice.bin.plugin_cli enable themed_hud
```

### Disable
```powershell
py -3.10 -m castervoice.bin.plugin_cli disable themed_hud
```

### Check Status
```powershell
py -3.10 -m castervoice.bin.plugin_cli list
```

---

## 3. Configuration (`settings.toml`)

Configuration is stored in `%LOCALAPPDATA%\caster\settings.toml`. The `[plugins.themed_hud]` section controls visual appearance and layout:

```toml
[plugins.themed_hud]
enabled = true
theme = "tokyo_night"
opacity = 0.92
font_size = 10
history_limit = 50
show_adce_strip = true
```

### Available Themes

* `tokyo_night` (default dark blue/purple)
* `catppuccin_mocha` (soft pastel dark)
* `nord` (arctic cold dark)
* `dracula` (high-contrast dark)
* `monokai_pro` (vibrant classic dark)
* `gruvbox_dark` (warm retro dark)
* `solarized_dark` / `solarized_light`
* `cyberpunk` (neon high-contrast)

---

## 4. How It Operates

1. **Process Architecture**:
   - The HUD runs in an asynchronous subprocess to ensure UI rendering never blocks the Caster voice recognition loop.
   - IPC communication between Caster and the HUD occurs over a local socket connection.

2. **Integration with Other Plugins**:
   - **ADCE**: When `adce` is enabled, the HUD renders an active context strip displaying the current sub-window zone and focused file.
   - **Mic telemetry**: Automatically displays microphone state changes (`on`, `sleeping`, `off`).

3. **Enabling and Disabling**:
   - When enabled, it replaces the default rudimentary Tkinter/text HUD with the Qt overlay.
   - When disabled (`enabled = false`), Caster falls back to standard text console logging or core HUD.
