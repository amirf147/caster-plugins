# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Launcher script to start the Caster Plugin Manager GUI.
"""

from pathlib import Path
import sys

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins.plugin_manager.gui.runner import main  # noqa: E402

if __name__ == "__main__":
    main()
