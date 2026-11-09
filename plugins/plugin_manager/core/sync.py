# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Cross-platform file synchronization engine for Caster plugins.
Safely mirrors plugin source packages from repository checkouts into Caster's live user directory.
"""

import hashlib
import logging
import os
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional, Set, Union

_logger = logging.getLogger("caster.plugins.plugin_manager.sync")

# File patterns to exclude from synchronization
EXCLUDED_PATTERNS: Set[str] = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".gitignore",
    ".DS_Store",
    "config.toml",  # Preserve local user config overrides in destination
}

EXCLUDED_EXTENSIONS: Set[str] = {
    ".pyc",
    ".pyo",
    ".tmp",
    ".bak",
}


def compute_file_sha256(file_path: Path) -> str:
    """Calculates SHA-256 hash of a file for deterministic content equality."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def should_ignore(path: Path) -> bool:
    """Returns True if the path or any of its components match exclusion rules."""
    for part in path.parts:
        if part in EXCLUDED_PATTERNS or part.startswith(".bak_"):
            return True
    if path.suffix.lower() in EXCLUDED_EXTENSIONS:
        return True
    return False


def resolve_default_target_dir() -> Path:
    """Resolves the standard destination directory in Caster user space."""
    user_dir_env = os.environ.get("CASTER_USER_DIR")
    if user_dir_env:
        return Path(user_dir_env).resolve() / "caster_user_content" / "plugins"

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data).resolve() / "caster" / "caster_user_content" / "plugins"

    return Path.home() / ".caster" / "caster_user_content" / "plugins"


class PluginSyncEngine:
    """
    Synchronizes plugin directory trees between source repository and live user space.
    Operates identically across Windows, Linux, and macOS.
    """

    def __init__(
        self,
        source_dir: Optional[Union[str, Path]] = None,
        target_dir: Optional[Union[str, Path]] = None,
    ):
        if target_dir is None:
            self._target_dir = resolve_default_target_dir()
        else:
            self._target_dir = Path(target_dir).resolve()

        if source_dir is None:
            resolved = self.resolve_local_source_dir(target_dir=self._target_dir)
            if resolved is not None:
                self._source_dir = resolved
            else:
                current_file = Path(__file__).resolve()
                self._source_dir = current_file.parents[2]
        else:
            self._source_dir = Path(source_dir).resolve()

    @classmethod
    def resolve_local_source_dir(cls, target_dir: Optional[Union[str, Path]] = None) -> Optional[Path]:
        """
        Resolves local source plugins repository directory across environment variables,
        settings.toml configuration, manifest location, and workspace paths.
        Avoids returning the target user directory itself.
        """
        target = Path(target_dir).resolve() if target_dir is not None else resolve_default_target_dir()

        # 1. Environment variable override
        repo_env = os.environ.get("CASTER_PLUGINS_REPO")
        if repo_env:
            p = Path(repo_env).resolve()
            cand = p if p.name == "plugins" else (p / "plugins")
            if cand.is_dir() and cand.resolve() != target:
                return cand.resolve()

        # 2. Local registry path in settings.toml
        try:
            from .storage import resolve_caster_settings_path
            settings_path = resolve_caster_settings_path()
            if settings_path.exists():
                import tomlkit
                with open(settings_path, "r", encoding="utf-8") as f:
                    doc = tomlkit.parse(f.read())
                reg_path = doc.get("plugins_config", {}).get("local_registry_path")
                if reg_path:
                    cand = Path(reg_path).resolve().parent / "plugins"
                    if cand.is_dir() and cand.resolve() != target:
                        return cand.resolve()
        except Exception:
            pass

        # 3. Repository root relative to this file
        current_file = Path(__file__).resolve()
        possible_manifest = current_file.parents[3] / "manifest.json"
        if possible_manifest.exists():
            cand = possible_manifest.parent / "plugins"
            if cand.is_dir() and cand.resolve() != target:
                return cand.resolve()

        # 4. Standard developer workspace paths
        for dev_cand in [
            Path.home() / "Documents" / "repos" / "caster-plugins" / "plugins",
            current_file.parents[2],
        ]:
            if dev_cand.is_dir() and dev_cand.resolve() != target:
                return dev_cand.resolve()

        return None

    @property
    def source_dir(self) -> Path:
        return self._source_dir

    @property
    def target_dir(self) -> Path:
        return self._target_dir

    def discover_source_plugins(self) -> List[str]:
        """Returns list of plugin package directory names available in source repository."""
        if not self._source_dir.exists() or not self._source_dir.is_dir():
            return []

        plugins = []
        for child in sorted(self._source_dir.iterdir()):
            if not child.is_dir() or child.name.startswith((".", "_")):
                continue
            if (child / "metadata.toml").exists() or (child / "plugin.py").exists() or (child / "__init__.py").exists():
                plugins.append(child.name)
        return plugins

    def get_plugin_drift(self, plugin_name: str) -> Dict[str, Any]:
        """
        Audits file drift between source and target directories for a single plugin.
        """
        src_plugin = self._source_dir / plugin_name
        dst_plugin = self._target_dir / plugin_name

        if not src_plugin.exists() or not src_plugin.is_dir():
            return {
                "plugin_name": plugin_name,
                "status": "missing_in_source",
                "added_files": [],
                "modified_files": [],
                "stale_files": [],
                "unchanged_files": [],
            }

        if not dst_plugin.exists() or not dst_plugin.is_dir():
            all_src_files = [
                str(p.relative_to(src_plugin))
                for p in src_plugin.rglob("*")
                if p.is_file() and not should_ignore(p)
            ]
            return {
                "plugin_name": plugin_name,
                "status": "missing_in_target",
                "added_files": sorted(all_src_files),
                "modified_files": [],
                "stale_files": [],
                "unchanged_files": [],
            }

        added: List[str] = []
        modified: List[str] = []
        stale: List[str] = []
        unchanged: List[str] = []

        src_files: Dict[str, Path] = {}
        for p in src_plugin.rglob("*"):
            if p.is_file() and not should_ignore(p):
                rel = str(p.relative_to(src_plugin)).replace("\\", "/")
                src_files[rel] = p

        dst_files: Dict[str, Path] = {}
        for p in dst_plugin.rglob("*"):
            if p.is_file() and not should_ignore(p):
                rel = str(p.relative_to(dst_plugin)).replace("\\", "/")
                dst_files[rel] = p

        for rel, src_path in src_files.items():
            if rel not in dst_files:
                added.append(rel)
            else:
                dst_path = dst_files[rel]
                if compute_file_sha256(src_path) == compute_file_sha256(dst_path):
                    unchanged.append(rel)
                else:
                    modified.append(rel)

        for rel in dst_files:
            if rel not in src_files:
                stale.append(rel)

        status = "synced" if (not added and not modified and not stale) else "drifted"

        return {
            "plugin_name": plugin_name,
            "status": status,
            "added_files": sorted(added),
            "modified_files": sorted(modified),
            "stale_files": sorted(stale),
            "unchanged_files": sorted(unchanged),
        }

    def get_all_drift(self) -> Dict[str, Dict[str, Any]]:
        """Audits drift across all available source plugins."""
        plugins = self.discover_source_plugins()
        return {p: self.get_plugin_drift(p) for p in plugins}

    def sync_plugin(
        self,
        plugin_name: str,
        dry_run: bool = False,
        prune_stale: bool = True,
    ) -> Dict[str, Any]:
        """
        Synchronizes a single plugin package from source to target.
        """
        drift = self.get_plugin_drift(plugin_name)
        if drift["status"] == "missing_in_source":
            raise FileNotFoundError(f"Plugin '{plugin_name}' not found in source directory {self._source_dir}")

        src_plugin = self._source_dir / plugin_name
        dst_plugin = self._target_dir / plugin_name

        copied: List[str] = []
        deleted: List[str] = []

        if not dry_run:
            dst_plugin.mkdir(parents=True, exist_ok=True)

            # Copy added and modified files
            for rel in drift["added_files"] + drift["modified_files"]:
                src_file = src_plugin / Path(rel)
                dst_file = dst_plugin / Path(rel)
                dst_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dst_file)
                copied.append(rel)

            # Prune stale files if requested
            if prune_stale:
                for rel in drift["stale_files"]:
                    dst_file = dst_plugin / Path(rel)
                    if dst_file.exists():
                        try:
                            dst_file.unlink()
                            deleted.append(rel)
                        except OSError as ex:
                            _logger.warning("Failed to remove stale file %s: %s", dst_file, ex)

                # Clean up empty parent directories
                for root, dirs, files in os.walk(dst_plugin, topdown=False):
                    if not dirs and not files and Path(root) != dst_plugin:
                        try:
                            os.rmdir(root)
                        except OSError:
                            pass

        return {
            "plugin_name": plugin_name,
            "dry_run": dry_run,
            "copied": sorted(copied if not dry_run else (drift["added_files"] + drift["modified_files"])),
            "deleted": sorted(deleted if not dry_run else drift["stale_files"]),
            "unchanged_count": len(drift["unchanged_files"]),
        }

    def sync_all(
        self,
        dry_run: bool = False,
        prune_stale: bool = True,
    ) -> Dict[str, Dict[str, Any]]:
        """Synchronizes all source plugins into target user directory."""
        plugins = self.discover_source_plugins()
        results = {}
        for name in plugins:
            results[name] = self.sync_plugin(name, dry_run=dry_run, prune_stale=prune_stale)
        return results

    def discover_target_plugins(self) -> List[str]:
        """Returns list of plugin package directory names present in target user directory."""
        if not self._target_dir.exists() or not self._target_dir.is_dir():
            return []

        plugins = []
        for child in sorted(self._target_dir.iterdir()):
            if not child.is_dir() or child.name.startswith((".", "_")):
                continue
            if (child / "metadata.toml").exists() or (child / "plugin.py").exists() or (child / "__init__.py").exists():
                plugins.append(child.name)
        return plugins

    def get_orphaned_plugins(self) -> List[str]:
        """Returns list of plugin names present in target directory but absent from source repository."""
        source_plugins = set(self.discover_source_plugins())
        return [p for p in self.discover_target_plugins() if p not in source_plugins]

    def prune_orphaned_plugins(self, dry_run: bool = False) -> List[str]:
        """Removes plugin directories in target directory that no longer exist in source repository."""
        orphaned = self.get_orphaned_plugins()
        pruned = []
        for name in orphaned:
            target_plugin = self._target_dir / name
            if not dry_run and target_plugin.exists():
                try:
                    shutil.rmtree(target_plugin, ignore_errors=False)
                    pruned.append(name)
                except OSError as ex:
                    _logger.warning("Failed to remove orphaned plugin directory %s: %s", target_plugin, ex)
            else:
                pruned.append(name)
        return pruned
