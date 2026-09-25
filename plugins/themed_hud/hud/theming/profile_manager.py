"""
Persistent Profile Manager for Storing and Restoring Named HUD Layouts.
"""

import json
import os
from typing import Dict, Any, List

PROFILES_FILE = os.path.expanduser("~/.caster/hud_profiles.json")


class ProfileManager:
    """
    Manages loading, saving, and deleting named HUD profiles.
    """

    def __init__(self, file_path: str = PROFILES_FILE):
        self._file_path = file_path
        self._ensure_dir()

    def _ensure_dir(self):
        dir_name = os.path.dirname(self._file_path)
        if dir_name and not os.path.exists(dir_name):
            try:
                os.makedirs(dir_name, exist_ok=True)
            except Exception:
                pass

    def load_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        if not os.path.isfile(self._file_path):
            return {}
        try:
            with open(self._file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_profile(self, name: str, state: Dict[str, Any]):
        profiles = self.load_all_profiles()
        profiles[name.lower().strip()] = state
        try:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(profiles, f, indent=2)
        except Exception:
            pass

    def load_profile(self, name: str) -> Dict[str, Any]:
        profiles = self.load_all_profiles()
        return profiles.get(name.lower().strip(), {})

    def delete_profile(self, name: str):
        profiles = self.load_all_profiles()
        clean_name = name.lower().strip()
        if clean_name in profiles:
            del profiles[clean_name]
            try:
                with open(self._file_path, "w", encoding="utf-8") as f:
                    json.dump(profiles, f, indent=2)
            except Exception:
                pass

    def list_profiles(self) -> List[str]:
        return sorted(list(self.load_all_profiles().keys()))
