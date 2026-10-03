# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Themed HUD Context Resolver

Re-exports unified context resolution logic from plugins.common.context_resolver.
"""

__all__ = [
    "RuleCatalog",
    "RuleEntry",
    "format_display_name",
    "get_catalog",
    "normalize_process_name",
    "resolve_active_rules",
    "resolve_caster_user_dir",
    "resolve_rule_search_dirs",
    "resolve_rules_config_path",
]

try:
    from plugins.common.context_resolver import (
        RuleCatalog,
        RuleEntry,
        format_display_name,
        get_catalog,
        normalize_process_name,
        resolve_active_rules,
        resolve_caster_user_dir,
        resolve_rule_search_dirs,
        resolve_rules_config_path,
    )
except ImportError:
    try:
        from ..common.context_resolver import (
            RuleCatalog,
            RuleEntry,
            format_display_name,
            get_catalog,
            normalize_process_name,
            resolve_active_rules,
            resolve_caster_user_dir,
            resolve_rule_search_dirs,
            resolve_rules_config_path,
        )
    except ImportError:
        from caster_user_content.plugins.common.context_resolver import (
            RuleCatalog,
            RuleEntry,
            format_display_name,
            get_catalog,
            normalize_process_name,
            resolve_active_rules,
            resolve_caster_user_dir,
            resolve_rule_search_dirs,
            resolve_rules_config_path,
        )
