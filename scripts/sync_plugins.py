# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Command-line utility to synchronize Caster plugins from the repository checkout
into Caster's live user content directory (%LOCALAPPDATA%\\caster\\caster_user_content\\plugins).
"""

import argparse
from pathlib import Path
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins.plugin_manager.core.sync import PluginSyncEngine  # noqa: E402


def format_status_table(all_drift: dict) -> str:
    """Formats drift report into a clean readable table."""
    lines = [
        f"{'Plugin Name':<20} {'Status':<18} {'Added':<8} {'Modified':<10} {'Stale':<8} {'Unchanged':<10}",
        "-" * 76,
    ]
    for name, data in sorted(all_drift.items()):
        status = data["status"]
        added = len(data["added_files"])
        mod = len(data["modified_files"])
        stale = len(data["stale_files"])
        unchanged = len(data["unchanged_files"])
        lines.append(f"{name:<20} {status:<18} {added:<8} {mod:<10} {stale:<8} {unchanged:<10}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Synchronize Caster plugins between repository and user directory."
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Audit and display file drift status without copying files.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Perform synchronization, copying added and modified files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview synchronization operations without modifying files on disk.",
    )
    parser.add_argument(
        "--plugin",
        nargs="*",
        help="Optional list of specific plugin names to synchronize. Defaults to all.",
    )
    parser.add_argument(
        "--source-dir",
        type=str,
        help="Custom source directory containing plugins.",
    )
    parser.add_argument(
        "--target-dir",
        type=str,
        help="Custom destination directory (defaults to Caster user plugins folder).",
    )

    args = parser.parse_args()

    engine = PluginSyncEngine(
        source_dir=args.source_dir,
        target_dir=args.target_dir,
    )

    print(f"Source Directory: {engine.source_dir}")
    print(f"Target Directory: {engine.target_dir}")
    print()

    # Default to --status if neither --sync nor --status is explicitly passed
    if not args.sync or args.status:
        all_drift = engine.get_all_drift()
        print(format_status_table(all_drift))
        print()

    if args.sync:
        plugins_to_sync = args.plugin if args.plugin else engine.discover_source_plugins()
        if not plugins_to_sync:
            print("No plugins found to synchronize.")
            return

        mode_str = "[DRY RUN] " if args.dry_run else ""
        print(f"{mode_str}Synchronizing {len(plugins_to_sync)} plugin(s)...")

        for name in plugins_to_sync:
            try:
                res = engine.sync_plugin(name, dry_run=args.dry_run)
                copied = len(res["copied"])
                deleted = len(res["deleted"])
                unchanged = res["unchanged_count"]
                print(f"  - {name:<18}: {copied} copied/updated, {deleted} removed, {unchanged} unchanged")
                if res["copied"]:
                    for f in res["copied"]:
                        print(f"      + {f}")
                if res["deleted"]:
                    for f in res["deleted"]:
                        print(f"      - {f}")
            except Exception as ex:
                print(f"  - {name:<18}: ERROR ({ex})")

        print()
        print(f"{mode_str}Synchronization complete.")


if __name__ == "__main__":
    main()
