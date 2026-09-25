# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Voice commands for the Themed / Modular HUD Plugin.
Registered with Dragonfly GrammarManager when themed_hud is active.
"""

from dragonfly import MappingRule, Function, Choice
from castervoice.lib import control, printer
from castervoice.lib.ctrl.mgr.rule_details import RuleDetails


def _get_hud():
    return control.nexus().comm.get_com("hud")


def _show_help():
    try:
        _get_hud().show_help()
    except Exception as e:
        printer.out("Themed HUD: show_help failed: {}".format(e))


def _show_theme_dialog():
    try:
        _get_hud().show_theme_dialog()
    except Exception as e:
        printer.out("Themed HUD: show_theme_dialog failed: {}".format(e))


def _set_theme(hud_theme):
    try:
        _get_hud().set_theme(str(hud_theme))
    except Exception as e:
        printer.out("Themed HUD: set_theme failed: {}".format(e))


def _cycle_theme():
    try:
        _get_hud().cycle_theme()
    except Exception as e:
        printer.out("Themed HUD: cycle_theme failed: {}".format(e))


def _toggle_drag():
    try:
        _get_hud().toggle_drag()
    except Exception as e:
        printer.out("Themed HUD: toggle_drag failed: {}".format(e))


def _toggle_status_bar():
    try:
        _get_hud().toggle_status_bar()
    except Exception as e:
        printer.out("Themed HUD: toggle_status_bar failed: {}".format(e))


def _toggle_rules_bar():
    try:
        _get_hud().toggle_rules_bar()
    except Exception as e:
        printer.out("Themed HUD: toggle_rules_bar failed: {}".format(e))


def _toggle_adce():
    try:
        _get_hud().toggle_adce()
    except Exception as e:
        printer.out("Themed HUD: toggle_adce failed: {}".format(e))


def _set_alignment(hud_alignment):
    try:
        _get_hud().set_text_alignment(str(hud_alignment))
    except Exception as e:
        printer.out("Themed HUD: set_alignment failed: {}".format(e))


def _set_opacity(opacity_val):
    try:
        _get_hud().set_opacity(float(opacity_val))
    except Exception as e:
        printer.out("Themed HUD: set_opacity failed: {}".format(e))


def _set_bg_opacity(opacity_val):
    try:
        _get_hud().set_background_opacity(float(opacity_val))
    except Exception as e:
        printer.out("Themed HUD: set_background_opacity failed: {}".format(e))


def _set_text_opacity(opacity_val):
    try:
        _get_hud().set_text_opacity(float(opacity_val))
    except Exception as e:
        printer.out("Themed HUD: set_text_opacity failed: {}".format(e))


def _font_increase():
    try:
        _get_hud().font_increase()
    except Exception as e:
        printer.out("Themed HUD: font_increase failed: {}".format(e))


def _font_decrease():
    try:
        _get_hud().font_decrease()
    except Exception as e:
        printer.out("Themed HUD: font_decrease failed: {}".format(e))


def _font_reset():
    try:
        _get_hud().font_reset()
    except Exception as e:
        printer.out("Themed HUD: font_reset failed: {}".format(e))


def _save_profile(name="default"):
    try:
        _get_hud().save_profile(str(name))
    except Exception as e:
        printer.out("Themed HUD: save_profile failed: {}".format(e))


def _load_profile(name="default"):
    try:
        _get_hud().load_profile(str(name))
    except Exception as e:
        printer.out("Themed HUD: load_profile failed: {}".format(e))


class ThemedHudRule(MappingRule):
    mapping = {
        "show caster [hud] help": Function(_show_help),
        "show caster [hud] (customize | themes | customizer)": Function(_show_theme_dialog),
        "caster hud theme <hud_theme>": Function(_set_theme),
        "caster hud cycle theme": Function(_cycle_theme),
        "caster hud [frameless] drag [mode] [toggle]": Function(_toggle_drag),
        "[caster hud] (status | header | status bar) [toggle]": Function(_toggle_status_bar),
        "[caster hud] (rules strip | active rules [strip] | rules bar | active rules) [toggle]": Function(_toggle_rules_bar),
        "[caster hud] (context strip | adce bar | adce) [toggle]": Function(_toggle_adce),
        "caster hud [text] align <hud_alignment>": Function(_set_alignment),
        "caster hud opacity <opacity_val>": Function(_set_opacity),
        "caster hud background opacity <opacity_val>": Function(_set_bg_opacity),
        "caster hud text opacity <opacity_val>": Function(_set_text_opacity),
        "caster hud font (bigger | increase)": Function(_font_increase),
        "caster hud font (smaller | decrease)": Function(_font_decrease),
        "caster hud font (reset | default)": Function(_font_reset),
        "caster hud save profile [name]": Function(_save_profile),
        "caster hud load profile [name]": Function(_load_profile),
    }

    extras = [
        Choice("hud_theme", {
            "classic": "classic",
            "frosted dark": "frosted-dark",
            "minimal transparent": "minimal-transparent",
            "high contrast": "high-contrast",
        }),
        Choice("hud_alignment", {
            "left": "left",
            "center": "center",
            "right": "right",
        }),
        Choice("opacity_val", {
            "ten": 0.1,
            "twenty": 0.2,
            "thirty": 0.3,
            "forty": 0.4,
            "fifty": 0.5,
            "sixty": 0.6,
            "seventy": 0.7,
            "eighty": 0.8,
            "ninety": 0.9,
            "one hundred": 1.0,
            "max": 1.0,
            "half": 0.5,
        }),
    ]


def get_rule():
    details = RuleDetails(name="Themed HUD Companion Rule")
    return ThemedHudRule, details
