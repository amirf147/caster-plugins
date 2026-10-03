# Plugin Manager Guide

The `plugin_manager` plugin provides an extensible management subsystem and Qt interface for Caster external plugins. It handles filesystem discovery, dependency validation, atomic state storage, declarative configuration schemas, and voice-driven subprocess orchestration.

---

## 1. System Architecture

The subsystem consists of three decoupled layers:

1. **Headless Core Engine (`core/`)**:
   - `PluginRegistry`: Main coordinator exposing query, toggle, configuration, and persistence APIs.
   - `PluginScanner`: Traverses filesystem directories, parsing `metadata.toml` descriptors and schema specifications.
   - `PluginValidator`: Enforces platform constraints and verifies required Python dependencies via `importlib.metadata`.
   - `StorageAdapter`: Provides atomic state persistence using temporary file writes and atomic replacement.
   - `PluginConfigStore`: Thread-safe per-plugin configuration storage adhering to declared option schemas.

2. **Qt Management Interface (`gui/`)**:
   - `PluginManagerWindow`: Top-level pop-up dialog with search filtering, status indicators, and tabbed inspection.
   - `PluginRowWidget`: Card widget displaying plugin identity, status chips, and state toggles.
   - `DetailPane`: Inspector tab providing metadata diagnostics and dependency audit logs.
   - `SettingsFormWidget`: Dynamic form builder mapping schema options (`bool`, `int`, `float`, `str`, `choice`) directly to interactive Qt controls.

3. **Subprocess Dispatcher & Voice Integration**:
   - `runner_bridge.py`: Non-blocking subprocess launcher with Win32 single-instance focus handling.
   - `plugin_manager_rule.py`: Companion Dragonfly voice rules exposing direct voice controls.

---

## 2. Voice Commands

| Voice Command | Action |
|---|---|
| `"plugin manager"` | Launches or focuses the Plugin Manager GUI window |
| `"plugin manager refresh"` | Triggers a live filesystem rescan across plugin directories |
| `"plugin manager close"` | Terminates or hides the active GUI process |
| `"enable plugin manager"` | Activates `PluginManagerRule` in Caster grammar activator |
| `"disable plugin manager"` | Deactivates `PluginManagerRule` in Caster grammar activator |

---

## 3. Standalone Execution

The interface can be launched directly from any PowerShell prompt without starting Caster:

```powershell
py -3.10 scripts/run_plugin_manager.py
```

Alternatively, launch the runner module directly:

```powershell
py -3.10 -m plugins.plugin_manager.gui.runner
```

---

## 4. Declarative Options Schema

Plugins declare configurable parameters by defining `[options.<key>]` tables in their `metadata.toml`:

```toml
[plugin]
name = "example_plugin"
version = "1.0.0"
description = "Example plugin with schema options"

[options.telemetry_enabled]
type = "bool"
default = true
description = "Enable real-time telemetry streaming"

[options.port]
type = "int"
default = 8424
min = 1024
max = 65535
description = "Network port for local IPC bridge"

[options.theme]
type = "choice"
default = "dark"
choices = ["dark", "light", "high_contrast"]
description = "Active UI theme"
```

The `SettingsFormWidget` automatically builds the corresponding form fields with real-time validation, bound enforcement, and atomic saving to `%LOCALAPPDATA%\caster\caster_user_content\plugins\<name>\config.toml`.
