"""
Unit tests for Caster HUD Theme Manager, Custom Themes Engine, and QSS Generation.
"""

import os
import shutil
import tempfile
import unittest
from hud.theming.theme_manager import (
    ThemeManager,
    THEME_CLASSIC,
    THEME_FROSTED,
    THEME_MINIMAL,
    THEME_HIGH_CONTRAST,
    build_stylesheet,
)


class TestHudTheming(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="caster_test_themes_")
        self.custom_file = os.path.join(self.test_dir, "hud_custom_themes.json")
        ThemeManager.set_custom_file_path(self.custom_file)

    def tearDown(self):
        ThemeManager.set_custom_file_path(os.path.expanduser("~/.caster/hud_custom_themes.json"))
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_available_themes_includes_builtins(self):
        available = ThemeManager.get_available_themes()
        self.assertIn(THEME_CLASSIC, available)
        self.assertIn(THEME_FROSTED, available)
        self.assertIn(THEME_MINIMAL, available)
        self.assertIn(THEME_HIGH_CONTRAST, available)

    def test_builtin_theme_identification(self):
        self.assertTrue(ThemeManager.is_builtin_theme("classic"))
        self.assertTrue(ThemeManager.is_builtin_theme("frosted-dark"))
        self.assertTrue(ThemeManager.is_builtin_theme("frosted"))
        self.assertFalse(ThemeManager.is_builtin_theme("custom-neon"))

    def test_get_builtin_theme_data_and_colors(self):
        classic_data = ThemeManager.get_theme_data(THEME_CLASSIC)
        self.assertEqual(classic_data["background_color"], "#f0f0f0")
        self.assertEqual(classic_data["textedit_bg"], "#ffffff")
        self.assertEqual(classic_data["text_color"], "#000000")

        classic_colors = ThemeManager.get_theme_colors(THEME_CLASSIC)
        self.assertEqual(classic_colors["cmd_color"], "blue")
        self.assertEqual(classic_colors["sys_color"], "purple")
        self.assertEqual(classic_colors["err_color"], "red")

        frosted_data = ThemeManager.get_theme_data(THEME_FROSTED)
        self.assertEqual(frosted_data["background_color"], "#1e1e24")
        self.assertEqual(frosted_data["opacity"], 0.95)

    def test_save_and_load_custom_theme(self):
        custom_data = {
            "name": "Cyberpunk Neon",
            "background_color": "#0a0a12",
            "textedit_bg": "#12121e",
            "text_color": "#00ffcc",
            "accent_color": "#ff007f",
            "border_color": "#331144",
            "cmd_color": "#00ffcc",
            "sys_color": "#ff007f",
            "err_color": "#ff3333",
            "opacity": 0.88,
        }

        theme_id = ThemeManager.save_custom_theme("Cyberpunk Neon", custom_data)
        self.assertEqual(theme_id, "cyberpunk-neon")

        # Verify it appears in available themes
        available = ThemeManager.get_available_themes()
        self.assertIn("cyberpunk-neon", available)

        # Verify get_theme_data
        loaded = ThemeManager.get_theme_data("cyberpunk-neon")
        self.assertEqual(loaded["name"], "Cyberpunk Neon")
        self.assertEqual(loaded["text_color"], "#00ffcc")
        self.assertEqual(loaded["accent_color"], "#ff007f")
        self.assertEqual(loaded["opacity"], 0.88)

        # Verify stylesheet generation contains the custom colors (with opacity 0.88 -> rgba)
        stylesheet = ThemeManager.get_stylesheet("cyberpunk-neon")
        self.assertIn("rgba(10, 10, 18, 224)", stylesheet)
        self.assertIn("#00ffcc", stylesheet)
        self.assertIn("#ff007f", stylesheet)

    def test_delete_custom_theme(self):
        custom_data = {
            "name": "Temporary Theme",
            "background_color": "#111111",
            "text_color": "#eeeeee",
        }
        theme_id = ThemeManager.save_custom_theme("Temporary Theme", custom_data)
        self.assertIn(theme_id, ThemeManager.get_available_themes())

        deleted = ThemeManager.delete_custom_theme(theme_id)
        self.assertTrue(deleted)
        self.assertNotIn(theme_id, ThemeManager.get_available_themes())

    def test_cannot_delete_builtin_theme(self):
        self.assertFalse(ThemeManager.delete_custom_theme(THEME_CLASSIC))
        self.assertFalse(ThemeManager.delete_custom_theme(THEME_FROSTED))
        self.assertIn(THEME_CLASSIC, ThemeManager.get_available_themes())

    def test_build_stylesheet_helper(self):
        data = {
            "background_color": "#202020",
            "textedit_bg": "#181818",
            "text_color": "#f0f0f0",
            "accent_color": "#00aaee",
            "border_color": "#404040",
        }
        css = build_stylesheet(data)
        self.assertIn("background-color: #202020", css)
        self.assertIn("background-color: #181818", css)
        self.assertIn("color: #f0f0f0", css)
        self.assertIn("border: 1px solid #404040", css)
        self.assertIn("selection-background-color: #00aaee", css)

    def test_distinct_background_and_letter_opacity(self):
        data = {
            "background_color": "#1e1e24",
            "textedit_bg": "#18181c",
            "text_color": "#ffffff",
            "accent_color": "#2563eb",
            "border_color": "#3b3b4a",
            "cmd_color": "#3498db",
            "sys_color": "#9b59b6",
            "err_color": "#e74c3c",
            "background_opacity": 0.60,
            "text_opacity": 0.85,
        }
        css = build_stylesheet(data)
        # Background alpha: 0.60 * 255 = 153
        self.assertIn("rgba(30, 30, 36, 153)", css)
        self.assertIn("rgba(24, 24, 28, 153)", css)
        # Text/letter alpha: 0.85 * 255 = 217
        self.assertIn("rgba(255, 255, 255, 217)", css)

    def test_get_stylesheet_with_overridden_opacities(self):
        css = ThemeManager.get_stylesheet("classic", background_opacity=0.50, text_opacity=0.90)
        # Background alpha: 0.50 * 255 = 128 (classic bg #f0f0f0 -> 240, 240, 240)
        self.assertIn("rgba(240, 240, 240, 128)", css)
        # Letter alpha: 0.90 * 255 = 230 (classic text #000000 -> 0, 0, 0)
        self.assertIn("rgba(0, 0, 0, 230)", css)

        # Verify get_theme_colors with custom text opacity
        theme_id = ThemeManager.save_custom_theme("AlphaTheme", {
            "cmd_color": "#00ff00",
            "text_opacity": 0.70,
        })
        colors = ThemeManager.get_theme_colors("alphatheme")
        # 0.70 * 255 = 178
        self.assertIn("rgba(0, 255, 0, 178)", colors["cmd_color"])

    def test_theme_with_text_alignment(self):
        # Verify built-in themes have default text_alignment="left"
        data = ThemeManager.get_theme_data("classic")
        self.assertEqual(data.get("text_alignment"), "left")

        # Save and retrieve custom theme with text_alignment="right"
        theme_id = ThemeManager.save_custom_theme("RightAlignedTheme", {
            "background_color": "#111111",
            "text_alignment": "right",
        })
        loaded = ThemeManager.get_theme_data(theme_id)
        self.assertEqual(loaded.get("text_alignment"), "right")


if __name__ == "__main__":
    unittest.main()
