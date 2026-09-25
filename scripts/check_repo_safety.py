#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi
"""
Repository Safety, Secret, Path Hygiene & Manifest Checker for Caster Plugins
"""

import getpass
import json
import os
import re
import subprocess
import sys

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None

# Root directory of the repository
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IGNORED_DIRS = {
    ".git",
    ".vs",
    ".vscode",
    "bin",
    "obj",
    "node_modules",
    ".ruff_cache",
    ".idea",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
}

IGNORED_EXTENSIONS = {
    ".dll",
    ".exe",
    ".pdb",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".mp4",
    ".ico",
    ".svg",
    ".pyc",
    ".pyo",
    ".pyd",
    ".woff",
    ".woff2",
    ".ttf",
}

IGNORED_FILES = {
    ".test_cache.json",
}

# Regex patterns for private path hygiene
WINDOWS_USER_PATH_RE = re.compile(
    r"[A-Za-z]:(?:\\{1,4}|/)+(?:Users|Documents and Settings)(?:\\{1,4}|/)+",
    re.IGNORECASE,
)
USER_HOME_PATH_RE = re.compile(
    r"(?:[A-Za-z]:(?:\\{1,4}|/)+|/|\\{1,4})(?:Users|home|Documents and Settings)(?:\\{1,4}|/)+[A-Za-z0-9_.-]+(?:\\{1,4}|/)+",
    re.IGNORECASE,
)
UNIX_USER_PATH_RE = re.compile(r"^/(?:Users|home)/[A-Za-z0-9_.-]+(?:/|$)", re.IGNORECASE)
USER_FILE_URI_RE = re.compile(
    r"file:///(?:[A-Za-z]:/(?:Users|Documents and Settings|home)|(?:Users|home)/)",
    re.IGNORECASE,
)

# Dynamic runtime detection for active local environment username
try:
    CURRENT_USER = getpass.getuser()
    if CURRENT_USER and len(CURRENT_USER) > 1 and CURRENT_USER.lower() not in {"root", "runner", "github", "administrator", "system"}:
        ACTIVE_USER_PATH_RE = re.compile(
            rf"(?:\\{{1,4}}|/)+{re.escape(CURRENT_USER)}(?:\\{{1,4}}|/)+",
            re.IGNORECASE,
        )
    else:
        ACTIVE_USER_PATH_RE = None
except Exception:
    ACTIVE_USER_PATH_RE = None

# Secret & credential token patterns
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA|PGP)?\s?PRIVATE KEY-----"), "Private Key Header"),
    (re.compile(r"\b(?:sk|pk)_(?:live|test)_[0-9a-zA-Z]{24,}\b"), "API Key Token"),
    (re.compile(r"\bghp_[0-9a-zA-Z]{36}\b"), "GitHub Personal Access Token"),
    (re.compile(r"\beyJ[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]{20,}\b"), "JWT Token"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@(?!(?:example\.com|users\.noreply\.github\.com|domain\.com)\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.IGNORECASE), "Plain Email Address in Content"),
]


def check_file_hygiene(file_path: str, rel_path: str) -> list[str]:
    violations = []
    if rel_path == "scripts/check_repo_safety.py":
        return violations

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.read().splitlines()

        for line_no, line in enumerate(lines, start=1):
            if WINDOWS_USER_PATH_RE.search(line):
                violations.append(f"{rel_path}:{line_no}: Hardcoded Windows user directory path leak: {line.strip()[:100]}")
            if USER_HOME_PATH_RE.search(line):
                violations.append(f"{rel_path}:{line_no}: Hardcoded user profile directory path: {line.strip()[:100]}")
            if UNIX_USER_PATH_RE.search(line):
                violations.append(f"{rel_path}:{line_no}: Hardcoded Unix user home directory path: {line.strip()[:100]}")
            if ACTIVE_USER_PATH_RE and ACTIVE_USER_PATH_RE.search(line):
                violations.append(f"{rel_path}:{line_no}: Active OS user path component: {line.strip()[:100]}")
            if USER_FILE_URI_RE.search(line):
                violations.append(f"{rel_path}:{line_no}: Local user file URI (file:///): {line.strip()[:100]}")

            for pattern, desc in SECRET_PATTERNS:
                if pattern.search(line):
                    violations.append(f"{rel_path}:{line_no}: Potential secret/credential ({desc}): {line.strip()[:60]}...")

    except Exception as ex:
        violations.append(f"{rel_path}: Failed to read file ({ex})")

    return violations


def check_manifest_integrity() -> list[str]:
    violations = []
    manifest_path = os.path.join(REPO_ROOT, "manifest.json")
    if not os.path.exists(manifest_path):
        return ["manifest.json does not exist in repository root."]

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest_data = json.load(f)
    except Exception as e:
        return [f"manifest.json is not valid JSON: {e}"]

    if "version" not in manifest_data:
        violations.append("manifest.json missing 'version' field.")
    if "plugins" not in manifest_data or not isinstance(manifest_data["plugins"], dict):
        violations.append("manifest.json missing 'plugins' dictionary.")
        return violations

    for plugin_key, info in manifest_data["plugins"].items():
        rel_path = info.get("path")
        if not rel_path:
            violations.append(f"Plugin '{plugin_key}' in manifest.json is missing 'path'.")
            continue

        plugin_dir = os.path.join(REPO_ROOT, rel_path)
        if not os.path.isdir(plugin_dir):
            violations.append(f"Plugin '{plugin_key}' path does not exist on disk: {rel_path}")
            continue

        init_py = os.path.join(plugin_dir, "__init__.py")
        if not os.path.exists(init_py):
            violations.append(f"Plugin '{plugin_key}' missing __init__.py at {rel_path}/__init__.py")

        plugin_py = os.path.join(plugin_dir, "plugin.py")
        if not os.path.exists(plugin_py):
            violations.append(f"Plugin '{plugin_key}' missing plugin.py entry point at {rel_path}/plugin.py")

        metadata_path = os.path.join(plugin_dir, "metadata.toml")
        if not os.path.exists(metadata_path):
            violations.append(f"Plugin '{plugin_key}' missing metadata.toml at {rel_path}/metadata.toml")
        elif tomllib is not None:
            try:
                with open(metadata_path, "rb") as mf:
                    meta = tomllib.load(mf)
                meta_version = meta.get("version")
                manifest_version = info.get("version")
                if meta_version and manifest_version and meta_version != manifest_version:
                    violations.append(
                        f"Plugin '{plugin_key}' version mismatch: manifest.json has '{manifest_version}' "
                        f"but metadata.toml has '{meta_version}'"
                    )
            except Exception as e:
                violations.append(f"Failed to parse {rel_path}/metadata.toml: {e}")

    return violations


def check_git_tracked_binaries() -> list[str]:
    violations = []
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        for tracked in res.stdout.splitlines():
            ext = os.path.splitext(tracked)[1].lower()
            if ext in {".pyc", ".pyo", ".pyd", ".dll", ".exe", ".so", ".dylib"}:
                violations.append(f"Tracked binary/compiled file in git: {tracked}")
            if tracked.startswith(".venv/") or tracked.startswith("venv/"):
                violations.append(f"Tracked virtual environment file in git: {tracked}")
    except Exception:
        # Not a fatal error if git is unavailable in environment
        pass
    return violations


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print(f"Scanning repository for safety, secrets, path hygiene, and manifest integrity: {REPO_ROOT}")
    all_violations = []

    # 1. Manifest and metadata checks
    print("Checking manifest and plugin metadata...")
    manifest_violations = check_manifest_integrity()
    all_violations.extend(manifest_violations)

    # 2. Git tracked binary checks
    print("Checking git tracked file hygiene...")
    binary_violations = check_git_tracked_binaries()
    all_violations.extend(binary_violations)

    # 3. File content hygiene scan
    print("Scanning text files for private paths and secrets...")
    for root, dirs, files in os.walk(REPO_ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

        for file in files:
            if file in IGNORED_FILES:
                continue

            ext = os.path.splitext(file)[1].lower()
            if ext in IGNORED_EXTENSIONS:
                continue

            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, REPO_ROOT).replace("\\", "/")

            violations = check_file_hygiene(file_path, rel_path)
            all_violations.extend(violations)

    if all_violations:
        print(f"\n[FAILED] Found {len(all_violations)} hygiene violation(s):\n")
        for v in all_violations:
            print(f"  - {v}")
        print("\nPlease resolve the above issues before committing or publishing.")
        return 1

    print("\n[PASSED] Zero path leaks, secrets, binary artifacts, or manifest inconsistencies detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
