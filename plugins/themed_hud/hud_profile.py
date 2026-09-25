"""
HUD Profile Manager for Caster Heads-Up Display.

Handles named profile persistence (geometry, theme, font, opacity, frameless)
in ~/.caster/data/hud_profiles.toml.
"""

from pathlib import Path
import io
import tomlkit
from castervoice.lib import settings


class ProfileManager(object):
    """
    Manages loading, saving, and listing named HUD profiles.
    """

    DEFAULT_PROFILE_NAME = "default"

    def __init__(self):
        self._profiles_path = self._resolve_profiles_path()

    def _resolve_profiles_path(self):
        user_dir = settings.SETTINGS.get("paths", {}).get("USER_DIR") if settings.SETTINGS else None
        if user_dir:
            data_dir = Path(user_dir).joinpath("data")
            data_dir.mkdir(parents=True, exist_ok=True)
            return data_dir.joinpath("hud_profiles.toml")
        return Path("hud_profiles.toml")

    def load_all_profiles(self):
        """Load all profiles from TOML file."""
        if not self._profiles_path.is_file():
            return {}
        try:
            with io.open(str(self._profiles_path), "rt", encoding="utf-8") as f:
                content = f.read()
                if not content.strip():
                    return {}
                return tomlkit.loads(content).value
        except Exception:
            return {}

    def save_all_profiles(self, profiles_dict):
        """Save entire profiles dictionary to TOML file."""
        try:
            formatted = str(tomlkit.dumps(profiles_dict))
            with io.open(str(self._profiles_path), "wt", encoding="utf-8") as f:
                f.write(formatted)
        except Exception:
            pass

    def save_profile(self, name, config_dict):
        """Save or update a named profile."""
        profile_name = str(name).strip().lower() if name else self.DEFAULT_PROFILE_NAME
        profiles = self.load_all_profiles()
        profiles[profile_name] = config_dict
        self.save_all_profiles(profiles)
        return profile_name

    def load_profile(self, name):
        """Load a specific profile by name. Returns dict or None."""
        profile_name = str(name).strip().lower() if name else self.DEFAULT_PROFILE_NAME
        profiles = self.load_all_profiles()
        return profiles.get(profile_name)

    def list_profiles(self):
        """Return a sorted list of profile names."""
        profiles = self.load_all_profiles()
        return sorted(list(profiles.keys()))

    def delete_profile(self, name):
        """Delete a named profile."""
        profile_name = str(name).strip().lower() if name else self.DEFAULT_PROFILE_NAME
        profiles = self.load_all_profiles()
        if profile_name in profiles:
            del profiles[profile_name]
            self.save_all_profiles(profiles)
            return True
        return False
