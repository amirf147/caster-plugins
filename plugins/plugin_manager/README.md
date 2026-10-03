# Caster Plugin Manager

Lightweight, extensible plugin manager subsystem and Qt management interface for the Caster voice programming ecosystem.

---

## Key Features

- **Filesystem Discovery**: Scans plugin directories, parses `metadata.toml` manifests, and extracts declarative schema options.
- **Dependency & Platform Validation**: Evaluates operating system compatibility and Python package dependencies via `importlib.metadata`.
- **Atomic State Persistence**: Thread-safe, atomic JSON storage preventing corrupted state on sudden shutdowns.
- **Dynamic Configuration Forms**: Auto-generates type-safe settings forms (`bool`, `int`, `float`, `str`, `choice`) directly from schema definitions.
- **Qt Management Dialog**: Search-filtered listing, health status badges, tabbed inspection pane, and dark styling.
- **Voice Companion Rules**: Deterministic Dragonfly voice grammar (`"plugin manager"`, `"plugin manager refresh"`, `"plugin manager close"`).
- **Isolated Child Process**: Spawns GUI in an independent subprocess to preserve low-latency voice recognition threads.

---

## Directory Layout

```text
plugins/plugin_manager/
├── __init__.py               # Package exports
├── metadata.toml             # Manifest declaration
├── plugin.py                 # Caster PluginBase lifecycle hook
├── plugin_manager_rule.py    # Dragonfly voice companion rules
├── rules.py                  # Backward-compatibility re-export layer
├── runner_bridge.py          # Subprocess launcher & Win32 focus manager
├── core/
│   ├── models.py             # Data records (PluginRecord, PluginMetadata, PluginHealthState)
│   ├── options.py            # Declarative OptionDefinition & OptionType validation
│   ├── scanner.py            # Filesystem scanner & TOML metadata parser
│   ├── validator.py          # Platform & dependency requirement checker
│   ├── storage.py            # Atomic state storage adapter
│   ├── config_store.py       # Per-plugin configuration persistence
│   └── registry.py           # Headless coordinator API
└── gui/
    ├── window.py             # Top-level Qt dialog (QDialog)
    ├── theme.py              # Dark QSS stylesheet & color palette
    ├── runner.py             # Standalone Qt application entry point
    └── widgets/
        ├── plugin_row.py     # Individual plugin list card widget
        ├── detail_pane.py    # Overview & diagnostics inspection tab
        └── settings_form.py  # Schema-driven dynamic configuration form
```

---

## Programmatic API Usage

```python
from plugins.plugin_manager import PluginRegistry, PluginHealthState

registry = PluginRegistry()
records = registry.scan()

for record in records:
    print(f"Plugin: {record.metadata.name} [{record.health.value}]")
    print(f"  Enabled: {record.enabled}")

# Toggle plugin enabled state atomically
registry.set_enabled("themed_hud", True)
```

---

## Running Standalone

Launch the interface directly from the repository root:

```powershell
py -3.10 scripts/run_plugin_manager.py
```

---

## Running Tests

Execute the complete Plugin Manager test suite:

```powershell
py -3.10 -m pytest tests/test_plugin_manager_core.py tests/test_plugin_manager_gui.py tests/test_plugin_manager_options.py tests/test_plugin_manager_runtime.py
```
