# Caster Plugins Repository

Dedicated distribution repository for optional Caster plugins, visual overlays, and external bridges.

![Taskbar HUD & ADCE Live Telemetry](docs/media/taskbar_hud_adce_demo.gif)

> **Live Telemetry & Context In Action**: Combining [**`taskbar_hud`**](plugins/taskbar_hud) with the **`adce`** (Active Desktop Context Engine) plugin projects real-time speech hypotheses, executed commands, microphone states, and sub-window semantic focus zones directly into the Windows 11 Taskbar system tray.

---

## Overview
This repository hosts standalone plugins for the [Caster](https://github.com/dictation-toolbox/Caster) voice programming framework. By separating advanced integrations from Caster Core, the core repository remains minimal and focused strictly on grammar execution.

## Available Plugins

| Plugin | Version | Description | Target Environment |
|---|---|---|---|
| **`themed_hud`** | `2.0.0` | Modular PyQt Heads-Up Display with 10+ QSS themes, opacity sliders, status bar, and ADCE context strip. | Windows 10/11 Desktop Overlay |
| [**`taskbar_hud`**](plugins/taskbar_hud) | `1.1.0` | Named Pipe bridge projecting real-time speech telemetry directly into the Windows 11 Taskbar via [Caster Taskbar HUD](https://github.com/amirf147/caster-taskbar-hud) with event-driven Win32 hooks and two-phase context resolution. | Windows 11 Taskbar |
| **`adce`** | `1.0.0` | Active Desktop Context Engine SSE client providing sub-millisecond focus predicates for integrated terminals. | Local HTTP/SSE Port 8424 |
| [**`plugin_manager`**](plugins/plugin_manager) | `1.0.0` | Extensible plugin manager GUI and headless registry engine with schema-driven configuration and companion voice rules. | Desktop Pop-up Dialog |

---

## Shared Architecture (`plugins/common`)

All visual HUD plugins share a common foundation in `plugins/common`:
- **Unified Context Resolver ([`context_resolver.py`](plugins/common/context_resolver.py))**: Prioritizes active in-memory Caster runtime data (`nexus._grammar_manager._managed_rules`) with AST fallbacks for offline testing. Implements two-phase evaluation (Phase 1: executable/title filtering; Phase 2: safe `FuncContext` execution).
- **Shell Overlay Exclusions**: Automatically suppresses Windows Shell infrastructure windows (Alt+Tab overlays, taskbars, desktop backdrops) to prevent false-positive rule matches.
- **Plugin Lifecycle Fallbacks ([`plugin_base.py`](plugins/common/plugin_base.py))**: Provides standard base classes ensuring seamless execution across varied environments.

---

## Installation Workflow

Users install plugins into their personal user directory via the Caster plugin CLI:

```powershell
py -3.10 -m castervoice.bin.plugin_cli list
py -3.10 -m castervoice.bin.plugin_cli install taskbar_hud
```

Plugins install into `%LOCALAPPDATA%\caster\caster_user_content\plugins\<name>\` and activate automatically in `settings.toml`.

## Contributing a Plugin
Each plugin directory must contain:
1. `metadata.toml`: Declarative manifest defining name, version, description, and dependencies.
2. `plugin.py`: A subclass of `PluginBase` implementing `initialize()`, `start()`, and `stop()`.
3. `__init__.py`: Package export file.
