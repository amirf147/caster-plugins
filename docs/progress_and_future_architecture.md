# Progress Tracking & Future Architecture

## Current Progress & Delivered Enhancements

### 1. Plugin Manager: Local Repository Synchronization
- **GUI Integration:** Added the `Update from Local` action button to the Plugin Manager header toolbar in `plugins/plugin_manager/gui/window.py`.
- **Target & Source Resolution:** Integrated `PluginSyncEngine` with deterministic fallback paths (`CASTER_PLUGINS_REPO` environment variable, `local_registry_path` from `settings.toml`, and local repository workspace checkouts).
- **Safe Sync Execution:** Synchronizes live plugins into Caster user space (`caster_user_content/plugins/`) using SHA-256 content verification, pruning stale files while preserving user configurations. If no local repository is detected, displays a diagnostic configuration dialog.

### 2. ADCE: Decoupled Daemon Lifecycle
- **Path Resolution:** Added default repository fallback to `active-desktop-context-engine/src/ADCE.Daemon` when environment variables are absent.
- **Socket Liveness Verification:** Validates port `8424` before spawning. Connects immediately if already running without launching duplicate processes.
- **Decoupled Process Persistence:** Removed process-killing hooks (`taskkill`) from `AdcePlugin.stop()`. Disabling or reloading the plugin in Caster disconnects the bridge client while leaving the daemon running for external tools and future reconnects.

---

## Future Architecture & Backlog

### Item 1: Approach B - Instant Live Development via Directory Junctions
* **Concept:** Instead of copying plugin files into `caster_user_content/plugins/`, replace the installed directories with NTFS directory junctions (Windows) or symbolic links (POSIX) pointing directly to the Git repository checkout.
* **Benefits:** Eliminates manual file copying or synchronization steps. Edits in the repository checkout take effect immediately upon restarting Caster.
* **Trade-offs & Platform Constraints:**
  * **Windows Privileges:** Standard symbolic links require Windows Developer Mode or elevated privileges. NTFS directory junctions (`mklink /J` or `New-Item -ItemType Junction`) work without elevation, but are Windows-specific.
  * **Build & Cache Isolation:** Runtime artifacts (such as `__pycache__` and `.pytest_cache`) are written directly into the source repository tree, requiring strict `.gitignore` rules.
  * **Scanner Traversal:** Directory scanners must handle junction resolution gracefully without entering circular references or failing on broken link targets.

### Item 2: Streamlined Remote Update Pipeline
* **Concept:** Implement an automated in-app update mechanism driven by remote manifest releases on GitHub.
* **Pipeline Requirements:**
  * **Manifest Versioning:** Enforce synchronized version bumping across `metadata.toml` and root `manifest.json`.
  * **Download & Extraction:** Implement non-destructive ZIP extraction from GitHub releases into user space, with atomic temporary staging and SHA-256 integrity verification.
  * **Rollback Protection:** Automatically revert to previous plugin versions if a newly extracted plugin fails validation during Caster startup.
