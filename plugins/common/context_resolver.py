# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Amir Farhadi

"""
Automated Rule Catalog and Universal Context Resolver for Caster Plugins

Dynamically catalogs application and contextual voice rules across active
runtime memory (nexus) and disk directories, mapping target executables
and window titles directly to active rules synchronized with Caster's
rules.toml configuration and Dragonfly FuncContext predicates.
"""

import ast
import logging
import os
import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Union

_logger = logging.getLogger("caster.plugins.common.context_resolver")

_KNOWN_FUNCTION_CONTEXTS: Dict[str, Callable] = {}

_SHELL_EXCLUDED_CLASSES = frozenset(
    [
        "XamlExplorerHostIslandWindow",
        "TaskSwitcherWnd",
        "Shell_TrayWnd",
        "Shell_SecondaryTrayWnd",
        "Progman",
        "WorkerW",
        "Windows.UI.Core.CoreWindow",
        "DV2ControlHost",
    ]
)


def _get_window_class_name(hwnd: int) -> str:
    """Returns the Win32 window class name for a given window handle."""
    if not hwnd or sys.platform != "win32":
        return ""
    try:
        import ctypes

        buf = ctypes.create_unicode_buffer(256)
        if ctypes.windll.user32.GetClassNameW(hwnd, buf, 256):
            return buf.value
    except Exception:
        pass
    return ""


def _get_known_function_context(name: str) -> Optional[Callable]:
    """Dynamically resolves and caches known FunctionContext callables."""
    if not name or not isinstance(name, str):
        return None
    if name in _KNOWN_FUNCTION_CONTEXTS:
        return _KNOWN_FUNCTION_CONTEXTS[name]

    user_dir = resolve_caster_user_dir()
    if user_dir and str(user_dir) not in sys.path:
        sys.path.insert(0, str(user_dir))

    lookup_modules = [
        "caster_user_content.util.powershell_context",
        "caster_user_content.util",
        "castervoice.lib.context",
    ]
    for mod_name in lookup_modules:
        try:
            import importlib

            mod = importlib.import_module(mod_name)
            if hasattr(mod, name):
                fn = getattr(mod, name)
                _KNOWN_FUNCTION_CONTEXTS[name] = fn
                return fn
        except Exception:
            pass

    return None


def normalize_process_name(raw_process: Optional[str]) -> str:
    """Normalizes process name or executable path to lowercase stem."""
    if not raw_process:
        return ""
    p = str(raw_process).strip().lower().replace("/", "\\")
    return Path(p).stem


def format_display_name(raw_name: Optional[str], class_name: str, is_ccr: bool = False) -> str:
    """Formats a clean, human-readable display title for a rule."""
    name = str(raw_name).strip() if raw_name else class_name

    # Normalize common naming inconsistencies
    name = name.replace("fire fox", "firefox").replace("Fire Fox", "Firefox")

    # Strip generic suffixes
    for suffix in (" Rule", " rule", "Rule"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()

    # Determine if CCR
    ccr = is_ccr or any(class_name.endswith(x) for x in ("CCR", "CcrRule", "CCRRule", "Ccr"))
    for suffix in (" CCR", " Ccr", "CCR", "Ccr"):
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
            ccr = True
            break

    if ccr:
        name = f"{name} CCR"

    if name.islower():
        name = name.title()

    return name


def _eval_ast_value(val_node):
    """Safely extracts python literals, identifiers, or container values from AST nodes."""
    try:
        return ast.literal_eval(val_node)
    except Exception:
        pass
    if isinstance(val_node, ast.Constant):
        return val_node.value
    if isinstance(val_node, ast.Name):
        return val_node.id
    if isinstance(val_node, (ast.List, ast.Tuple)):
        items = []
        for elt in val_node.elts:
            v = _eval_ast_value(elt)
            if v is not None:
                items.append(v)
        return items
    if isinstance(val_node, ast.Attribute):
        return val_node.attr
    return None


def resolve_caster_user_dir() -> Optional[Path]:
    """Resolves Caster user directory across settings, env vars, OS standards, and fallbacks."""
    try:
        from castervoice.lib import settings

        if getattr(settings, "SETTINGS", None) and "paths" in settings.SETTINGS:
            p = settings.SETTINGS["paths"].get("USER_DIR")
            if p and Path(p).exists():
                return Path(p)
    except Exception:
        pass

    env_dir = os.environ.get("CASTER_USER_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)

    if os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            p = Path(local_app) / "caster"
            if p.exists():
                return p
    else:
        p = Path.home() / ".caster"
        if p.exists():
            return p

    cur = Path(__file__).resolve()
    for parent in cur.parents:
        if (parent / "settings" / "rules.toml").exists() or (parent / "caster_user_content").exists():
            return parent

    return None


def resolve_rules_config_path(user_dir: Optional[Path] = None) -> Optional[Path]:
    """Resolves rules.toml path across settings, user dir, and relative fallbacks."""
    try:
        from castervoice.lib import settings

        if getattr(settings, "SETTINGS", None) and "paths" in settings.SETTINGS:
            cfg_path = settings.SETTINGS["paths"].get("RULES_CONFIG_PATH")
            if cfg_path and Path(cfg_path).exists():
                return Path(cfg_path)
    except Exception:
        pass

    if user_dir:
        p = user_dir / "settings" / "rules.toml"
        if p.exists():
            return p

    if os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA")
        if local_app:
            p = Path(local_app) / "caster" / "settings" / "rules.toml"
            if p.exists():
                return p
    else:
        p = Path.home() / ".caster" / "settings" / "rules.toml"
        if p.exists():
            return p

    cur = Path(__file__).resolve()
    for parent in cur.parents:
        p = parent / "settings" / "rules.toml"
        if p.exists():
            return p

    return None


def resolve_rule_search_dirs(user_dir: Optional[Path] = None) -> List[Path]:
    """Discovers all rule directories: user content rules and core rules."""
    search_dirs: List[Path] = []

    def _add_dir(d: Optional[Path]):
        if d and d.exists() and d not in search_dirs:
            search_dirs.append(d)

    if user_dir:
        _add_dir(user_dir / "caster_user_content" / "rules")
        _add_dir(user_dir / "rules")

    if not search_dirs:
        if os.name == "nt":
            local_app = os.environ.get("LOCALAPPDATA")
            if local_app:
                base = Path(local_app) / "caster"
                _add_dir(base / "caster_user_content" / "rules")
                _add_dir(base / "rules")
        else:
            base = Path.home() / ".caster"
            _add_dir(base / "caster_user_content" / "rules")
            _add_dir(base / "rules")

    try:
        from castervoice.lib import settings

        if getattr(settings, "SETTINGS", None) and "paths" in settings.SETTINGS:
            bp = settings.SETTINGS["paths"].get("BASE_PATH")
            if bp:
                _add_dir(Path(bp) / "rules")
    except Exception:
        pass

    try:
        import castervoice

        _add_dir(Path(castervoice.__file__).parent / "rules")
    except Exception:
        pass

    cur = Path(__file__).resolve()
    for parent in cur.parents:
        _add_dir(parent / "caster_user_content" / "rules")
        _add_dir(parent / "rules")

    return search_dirs


def _evaluate_function_context(
    func_or_name: Union[Callable, str, None],
    process_name: str,
    window_title: str,
    semantic_zone: str,
    hwnd: int,
) -> bool:
    """Safely evaluates a Dragonfly FuncContext predicate against foreground window state."""
    if func_or_name is None:
        return True

    fn = None
    if callable(func_or_name):
        fn = func_or_name
    elif isinstance(func_or_name, str):
        fn = _get_known_function_context(func_or_name)

    if fn is None:
        return True

    try:
        return bool(fn(executable=process_name, title=window_title, semantic_zone=semantic_zone, handle=hwnd))
    except TypeError:
        try:
            return bool(fn(executable=process_name, title=window_title, handle=hwnd))
        except TypeError:
            try:
                return bool(fn(handle=hwnd))
            except TypeError:
                try:
                    return bool(fn())
                except Exception as ex:
                    _logger.debug("Exception invoking function_context: %s", ex)
                    return False
            except Exception as ex:
                _logger.debug("Exception invoking function_context: %s", ex)
                return False
        except Exception as ex:
            _logger.debug("Exception invoking function_context: %s", ex)
            return False
    except Exception as ex:
        _logger.debug("Exception invoking function_context: %s", ex)
        return False


class RuleEntry:
    __slots__ = (
        "rule_class",
        "display_name",
        "executables",
        "titles",
        "function_context",
        "is_ccr",
        "is_global",
    )

    def __init__(
        self,
        rule_class: str,
        display_name: str,
        executables: List[str],
        titles: List[str],
        function_context: Union[Callable, str, None] = None,
        is_ccr: bool = False,
        is_global: bool = False,
    ):
        self.rule_class = rule_class
        self.display_name = display_name
        self.executables = executables
        self.titles = titles
        self.function_context = function_context
        self.is_ccr = is_ccr
        self.is_global = is_global

    def __repr__(self) -> str:
        return f"<RuleEntry {self.rule_class} ({self.display_name})>"


class RuleCatalog:
    """
    In-memory catalog of all active and discovered voice rules.
    Prioritizes active runtime memory from Caster's GrammarManager when available,
    with an automated AST scanner fallback for standalone and testing environments.
    """

    def __init__(self):
        self._proc_map: Dict[str, List[RuleEntry]] = {}
        self._title_rules: List[RuleEntry] = []
        self._entries_by_class: Dict[str, RuleEntry] = {}
        self._enabled_rcns: Set[str] = set()
        self._user_dir: Optional[Path] = resolve_caster_user_dir()
        self._rules_config_path: Optional[Path] = resolve_rules_config_path(self._user_dir)
        self._last_config_mtime: float = 0.0
        self._catalog_built: bool = False
        self.refresh_catalog()

    def refresh_enabled(self):
        """Reloads enabled rule class names from rules.toml or runtime manager."""
        try:
            from castervoice.lib import control

            nexus = control.nexus()
            if nexus and hasattr(nexus, "_grammar_manager") and nexus._grammar_manager:
                gm = nexus._grammar_manager
                if hasattr(gm, "_config") and hasattr(gm._config, "get_enabled_rcns_ordered"):
                    enabled_list = gm._config.get_enabled_rcns_ordered()
                    if enabled_list:
                        self._enabled_rcns = set(str(x) for x in enabled_list)
                        return
        except Exception:
            pass

        if not self._rules_config_path or not self._rules_config_path.exists():
            return

        try:
            mtime = self._rules_config_path.stat().st_mtime
            if mtime != self._last_config_mtime:
                self._last_config_mtime = mtime
                data = None
                try:
                    from castervoice.lib import utilities

                    data = utilities.load_toml_file(str(self._rules_config_path))
                except Exception:
                    pass

                if data is None:
                    try:
                        if sys.version_info >= (3, 11):
                            import tomllib

                            with open(self._rules_config_path, "rb") as f:
                                data = tomllib.load(f)
                        else:
                            import tomli

                            with open(self._rules_config_path, "rb") as f:
                                data = tomli.load(f)
                    except Exception:
                        pass

                if isinstance(data, dict):
                    enabled_list = data.get("_enabled_ordered", [])
                    self._enabled_rcns = set(str(x) for x in enabled_list)
        except Exception as ex:
            _logger.debug("Failed to read rules.toml for enabled state: %s", ex)

    def _index_rule_details(self, rcn: str, rule_cls, details):
        """Indexes structured RuleDetails into candidate process and title tables."""
        raw_name = getattr(details, "name", None)
        declared_ccr = getattr(details, "declared_ccrtype", None)
        is_ccr = bool(declared_ccr) or (rule_cls and getattr(rule_cls, "_is_ccr", False))
        display = format_display_name(raw_name, rcn, is_ccr=is_ccr)

        raw_execs = getattr(details, "executable", None)
        if isinstance(raw_execs, str):
            execs = [raw_execs]
        elif isinstance(raw_execs, (list, tuple, set)):
            execs = list(raw_execs)
        else:
            execs = []
        exec_stems = [Path(str(e).strip().lower().replace("/", "\\")).stem for e in execs if e]

        raw_titles = getattr(details, "title", None)
        if isinstance(raw_titles, str):
            titles = [raw_titles]
        elif isinstance(raw_titles, (list, tuple, set)):
            titles = list(raw_titles)
        else:
            titles = []
        clean_titles = [str(t).lower() for t in titles if t]

        func_ctx = getattr(details, "function_context", None)
        is_global = not exec_stems and not clean_titles and declared_ccr != "app"

        entry = RuleEntry(
            rule_class=rcn,
            display_name=display,
            executables=exec_stems,
            titles=clean_titles,
            function_context=func_ctx,
            is_ccr=is_ccr,
            is_global=is_global,
        )
        self._entries_by_class[rcn] = entry

        if exec_stems:
            for stem in exec_stems:
                self._proc_map.setdefault(stem, []).append(entry)
        if clean_titles and not exec_stems:
            self._title_rules.append(entry)

    def _try_populate_from_runtime(self) -> bool:
        """Attempts to build the catalog directly from Caster's active in-memory GrammarManager."""
        try:
            from castervoice.lib import control

            nexus = control.nexus()
            if not nexus or not hasattr(nexus, "_grammar_manager") or not nexus._grammar_manager:
                return False

            gm = nexus._grammar_manager
            managed_rules = getattr(gm, "_managed_rules", {})
            if not managed_rules:
                return False

            self._proc_map.clear()
            self._title_rules.clear()
            self._entries_by_class.clear()

            if hasattr(gm, "_config") and hasattr(gm._config, "get_enabled_rcns_ordered"):
                enabled_list = gm._config.get_enabled_rcns_ordered()
                if enabled_list:
                    self._enabled_rcns = set(str(x) for x in enabled_list)

            for rcn, managed_rule in managed_rules.items():
                details = managed_rule.get_details()
                rule_cls = managed_rule.get_rule_class()
                self._index_rule_details(rcn, rule_cls, details)

            self._catalog_built = True
            return True
        except Exception as ex:
            _logger.debug("Failed to populate RuleCatalog from runtime: %s", ex)
            return False

    def refresh_catalog(self):
        """Builds or refreshes the rule catalog from runtime memory or disk AST."""
        if self._try_populate_from_runtime():
            return

        self._proc_map.clear()
        self._title_rules.clear()
        self._entries_by_class.clear()

        if not self._user_dir or not self._user_dir.exists():
            self._user_dir = resolve_caster_user_dir()
        if not self._rules_config_path or not self._rules_config_path.exists():
            self._rules_config_path = resolve_rules_config_path(self._user_dir)

        scan_dirs = resolve_rule_search_dirs(self._user_dir)

        for d in scan_dirs:
            if not d.exists():
                continue
            for p in d.rglob("*.py"):
                if p.name.startswith("_"):
                    continue
                self._parse_rule_file(p)

        self._catalog_built = True
        self.refresh_enabled()

    def _parse_rule_file(self, file_path: Path):
        """Inspects a rule module AST for get_rule() and RuleDetails metadata."""
        try:
            tree = ast.parse(file_path.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return

        rule_class = None
        details = {}
        has_get_rule = False

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "get_rule":
                has_get_rule = True
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call):
                        func_name = getattr(sub.func, "id", getattr(sub.func, "attr", ""))
                        if func_name == "RuleDetails":
                            for kw in sub.keywords:
                                val = _eval_ast_value(kw.value)
                                if val is not None:
                                    details[kw.arg] = val
                    if isinstance(sub, ast.Return):
                        ret_val = sub.value
                        if isinstance(ret_val, ast.Tuple) and len(ret_val.elts) >= 1:
                            elt0 = ret_val.elts[0]
                            rule_class = getattr(elt0, "id", getattr(elt0, "attr", None))
                        elif isinstance(ret_val, ast.Name):
                            rule_class = ret_val.id

        if has_get_rule and rule_class:
            class DummyDetails:
                pass

            d = DummyDetails()
            d.name = details.get("name")
            d.executable = details.get("executable")
            d.title = details.get("title")
            d.function_context = details.get("function_context")
            d.declared_ccrtype = details.get("ccrtype")

            self._index_rule_details(rule_class, None, d)

    def resolve(
        self,
        process_name: Optional[str] = None,
        window_title: Optional[str] = None,
        semantic_zone: Optional[str] = None,
        hwnd: int = 0,
    ) -> List[str]:
        """
        Deterministically resolves active contextual rules matching process, title,
        and runtime functional predicates.
        """
        if not self._catalog_built:
            self.refresh_catalog()
        else:
            self.refresh_enabled()

        proc = normalize_process_name(process_name)
        if not proc:
            return []

        candidates: List[RuleEntry] = []

        # 1. Base executable stem lookup
        if proc in self._proc_map:
            if proc == "explorer" and hwnd:
                cls_name = _get_window_class_name(hwnd)
                if cls_name in _SHELL_EXCLUDED_CLASSES:
                    # Shell infrastructure / Alt+Tab / Taskbar / Desktop: exclude folder explorer rules
                    pass
                else:
                    candidates.extend(self._proc_map[proc])
            else:
                candidates.extend(self._proc_map[proc])

        # 2. Terminal shell aliases in terminal host windows
        if proc in ("windowsterminal", "conhost", "cmd", "wt"):
            t_low = (window_title or "").lower()
            if "powershell" in t_low or "pwsh" in t_low:
                candidates.extend(self._proc_map.get("powershell", []))
                candidates.extend(self._proc_map.get("pwsh", []))

        # 3. Title-based website rules
        if window_title:
            t_low = window_title.lower()
            for r in self._title_rules:
                if any(t in t_low for t in r.titles):
                    candidates.append(r)

        # 4. Filter by enabled rules in rules.toml / runtime manager
        active_names: List[str] = []
        seen: Set[str] = set()

        for r in candidates:
            if self._enabled_rcns and r.rule_class not in self._enabled_rcns:
                continue

            # Phase 2: Functional Context Check
            if r.function_context is not None:
                matches_func = _evaluate_function_context(
                    r.function_context,
                    process_name=proc,
                    window_title=window_title or "",
                    semantic_zone=semantic_zone or "",
                    hwnd=hwnd,
                )
                if not matches_func:
                    continue

            name = r.display_name
            if name and name not in seen:
                seen.add(name)
                active_names.append(name)

        return active_names


_GLOBAL_CATALOG: Optional[RuleCatalog] = None


def get_catalog() -> RuleCatalog:
    global _GLOBAL_CATALOG
    if _GLOBAL_CATALOG is None:
        _GLOBAL_CATALOG = RuleCatalog()
    return _GLOBAL_CATALOG


def resolve_active_rules(
    process_name: Optional[str] = None,
    window_title: Optional[str] = None,
    semantic_zone: Optional[str] = None,
    hwnd: int = 0,
) -> List[str]:
    """
    Deterministically resolves active contextual voice rules from process, title,
    and runtime function predicates. Returns [] for generic or desktop contexts.
    """
    return get_catalog().resolve(
        process_name=process_name,
        window_title=window_title,
        semantic_zone=semantic_zone,
        hwnd=hwnd,
    )
