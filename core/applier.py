"""
Theme Applier — applies theme components to the Windows system.

Every _apply_* method returns {"success": bool, "message": str}.
Guide-type components additionally return {"guide": True, "guide_path": ..., "app": ...}.
"""

import ctypes
import json
import os
import shutil
import subprocess
import threading
from typing import Any

# Guarded winreg import so the module loads cleanly on non-Windows.
try:
    import winreg  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - non-Windows
    winreg = None  # type: ignore[assignment]

from core._io import atomic_write_json, safe_remove
from core.logger import log
from core.win32 import reg_open_key, reg_set_value, set_system_parameter


class Applier:
    """Central theme application engine."""

    # Concurrency lock to prevent overlapping apply operations
    _lock = threading.Lock()

    # Single dispatch dict — no duplication
    DISPATCH = {
        "msstyles": "_apply_msstyles",
        "wallpapers": "_apply_wallpaper",
        "cursors": "_apply_cursors",
        "fonts": "_apply_fonts",
        "terminal": "_apply_terminal",
        "firefox": "_apply_firefox",
        "windhawk": "_apply_windhawk",
        "themes": "_apply_themes",
        "startorb": "_apply_startorb",
        "startallback": "_apply_startallback",
        "mica": "_apply_mica",
        "oldnewexplorer": "_apply_oldnewexplorer",
        "resource_redirect": "_apply_resource_redirect",
        "icons": "_apply_icons",
    }

    def __init__(self, theme_manager):
        self.theme_manager = theme_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def apply_full_theme(self, theme_name: str) -> dict[str, dict[str, Any]]:
        theme = self.theme_manager.get_theme(theme_name)
        if not theme:
            raise ValueError(f"Theme not found: {theme_name}")

        manifest = theme["manifest"]
        components = manifest.get("components", {})
        results: dict[str, dict[str, Any]] = {}

        for comp_type, comp_data in components.items():
            method_name = self.DISPATCH.get(comp_type)
            if not method_name:
                log.warning("Unknown component type: %s", comp_type)
                continue
            variant_name = self.theme_manager.active_components.get(comp_type)
            try:
                results[comp_type] = getattr(self, method_name)(
                    theme_name, comp_data, variant_name
                )
            except Exception as exc:
                log.exception("Error applying %s", comp_type)
                results[comp_type] = {"success": False, "message": str(exc)}

        return results

    def apply_component(
        self, theme_name: str, component_type: str, variant_name: str | None = None
    ) -> dict[str, Any]:
        theme = self.theme_manager.get_theme(theme_name)
        if not theme:
            raise ValueError(f"Theme not found: {theme_name}")

        components = theme["manifest"].get("components", {})
        comp_data = components.get(component_type, {})

        method_name = self.DISPATCH.get(component_type)
        if not method_name:
            raise ValueError(f"Unknown component type: {component_type}")

        return getattr(self, method_name)(theme_name, comp_data, variant_name)

    def restore_defaults(self) -> dict[str, dict[str, Any]]:
        """Revert system to default theme elements.

        Now handles msstyles, wallpaper, cursors, start orb, fonts, terminal,
        firefox, windhawk, and resource redirect — not just the first three.
        """
        results: dict[str, dict[str, Any]] = {}

        # 1. Restore default msstyles / theme
        try:
            default_theme = os.path.join(
                os.environ.get("WINDIR", r"C:\Windows"), "Resources", "Themes", "aero.theme"
            )
            if os.path.exists(default_theme):
                with reg_open_key(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes",
                    writable=True,
                ) as key:
                    reg_set_value(key, "CurrentTheme", default_theme)
                ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "ImmersiveColorSet")
                results["msstyles"] = {"success": True, "message": "Reverted to Aero theme"}
            else:
                results["msstyles"] = {"success": False, "message": "Default aero.theme not found"}
        except Exception as exc:
            results["msstyles"] = {"success": False, "message": str(exc)}

        # 2. Restore default wallpaper
        try:
            default_wallpaper = os.path.join(
                os.environ.get("WINDIR", r"C:\Windows"), "Web", "Wallpaper", "Windows", "img0.jpg"
            )
            if os.path.exists(default_wallpaper):
                ok, msg = set_system_parameter(20, 0, default_wallpaper, 3)
                if ok:
                    results["wallpapers"] = {"success": True, "message": "Wallpaper reset to default"}
                else:
                    results["wallpapers"] = {"success": False, "message": f"Wallpaper reset failed: {msg}"}
            else:
                results["wallpapers"] = {"success": True, "message": "Default wallpaper not found, skipped"}
        except Exception as exc:
            results["wallpapers"] = {"success": False, "message": str(exc)}

        # 3. Reset cursors
        try:
            with reg_open_key(
                winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", writable=True
            ) as key:
                reg_set_value(key, "", "")
                reg_set_value(key, "Scheme Source", 0)
            # Broadcast SPI_SETCURSORS so the change takes effect immediately.
            ok, msg = set_system_parameter(0x0057, 0, None, 2)
            if not ok:
                log.warning("restore_defaults: cursor broadcast failed: %s", msg)
            results["cursors"] = {"success": True, "message": "Cursors reset to system default"}
        except Exception as exc:
            results["cursors"] = {"success": False, "message": str(exc)}

        # 4. Clear start orbs (both SAB and Windhawk)
        try:
            local = os.environ.get("LOCALAPPDATA", "")
            orb_dirs = [
                r"C:\StartAllBack\Orbs",
                os.path.join(local, "StartAllBack", "Orbs"),
                r"C:\Windhawk\StartOrbs",
            ]
            cleared = 0
            for orb_dir in orb_dirs:
                if os.path.isdir(orb_dir):
                    for f in os.listdir(orb_dir):
                        if safe_remove(os.path.join(orb_dir, f)):
                            cleared += 1
            results["startorb"] = {"success": True, "message": f"Cleared {cleared} custom start orb(s)"}
        except Exception as exc:
            results["startorb"] = {"success": False, "message": str(exc)}

        # 5. Clear windhawk mods
        try:
            windhawk_path = os.path.join(
                os.environ.get("APPDATA", ""), "Windhawk", "ModsWritable"
            )
            if os.path.isdir(windhawk_path):
                count = 0
                for f in os.listdir(windhawk_path):
                    fpath = os.path.join(windhawk_path, f)
                    if os.path.isfile(fpath) and safe_remove(fpath):
                        count += 1
                results["windhawk"] = {"success": True, "message": f"Cleared {count} Windhawk mod files"}
            else:
                results["windhawk"] = {"success": True, "message": "Windhawk mods directory not found"}
        except Exception as exc:
            results["windhawk"] = {"success": False, "message": str(exc)}

        # 7. Fonts note
        results["fonts"] = {
            "success": True,
            "message": "Fonts were installed system-wide — remove manually via Settings > Fonts",
        }

        # 8. Terminal schemes note
        results["terminal"] = {
            "success": True,
            "message": "Terminal schemes were added — remove manually in Terminal settings",
        }

        # 9. Firefox cleanup
        try:
            firefox_path = os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox")
            if os.path.isdir(firefox_path):
                cleared = 0
                for entry in os.listdir(firefox_path):
                    profile_chrome = os.path.join(firefox_path, entry, "chrome")
                    if os.path.isdir(profile_chrome):
                        for f in os.listdir(profile_chrome):
                            fpath = os.path.join(profile_chrome, f)
                            if os.path.isfile(fpath) and f.endswith((".css", ".js", ".xml")):
                                if safe_remove(fpath):
                                    cleared += 1
                results["firefox"] = {"success": True, "message": f"Cleaned {cleared} Firefox chrome files"}
            else:
                results["firefox"] = {"success": True, "message": "Firefox directory not found"}
        except Exception as exc:
            results["firefox"] = {"success": False, "message": str(exc)}

        # 10. Resource redirect cleanup
        try:
            resources_dir = r"C:\Windhawk\Resources"
            if os.path.isdir(resources_dir):
                for entry in os.listdir(resources_dir):
                    epath = os.path.join(resources_dir, entry)
                    if os.path.isdir(epath):
                        shutil.rmtree(epath, ignore_errors=True)
                results["resource_redirect"] = {"success": True, "message": "Cleared resource redirect files"}
            else:
                results["resource_redirect"] = {"success": True, "message": "Resource redirect directory not found"}
        except Exception as exc:
            results["resource_redirect"] = {"success": False, "message": str(exc)}

        return results

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve(self, theme_name: str, relative_path: str) -> str | None:
        return self.theme_manager.resolve_component_path(theme_name, relative_path)

    def _get_variant(self, component: dict, variant_name: str | None) -> dict | None:
        variants = component.get("variants", [])
        if not variants:
            return None
        if variant_name:
            for v in variants:
                if v.get("name") == variant_name:
                    return v
        return variants[0]

    def _find_sab_styles_dir(self) -> str | None:
        """Locate StartAllBack Styles directory. Returns None if not found."""
        candidates = [
            r"C:\StartAllBack\Styles",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "StartAllBack", "Styles"),
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "StartAllBack", "Styles"),
        ]
        for d in candidates:
            if os.path.isdir(d):
                return d
        log.warning("StartAllBack Styles dir not found")
        return None

    def _find_sab_orbs_dir(self) -> str | None:
        """Locate StartAllBack Orbs directory. Returns None if not found."""
        candidates = [
            r"C:\StartAllBack\Orbs",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "StartAllBack", "Orbs"),
            os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "StartAllBack", "Orbs"),
        ]
        for d in candidates:
            if os.path.isdir(d):
                return d
        log.warning("StartAllBack Orbs dir not found")
        return None

    def _resolve_orb_dir(self, target: str) -> str:
        """Resolve the correct orb destination based on target type."""
        if target == "startallback":
            return self._find_sab_orbs_dir()

        if target == "windhawk":
            return r"C:\Windhawk\StartOrbs"

        # Auto-detect: if SAB root exists, prefer it
        if os.path.isdir(r"C:\StartAllBack"):
            return r"C:\StartAllBack\Orbs"

        local = os.environ.get("LOCALAPPDATA", "")
        sab_dir = os.path.join(local, "StartAllBack")
        if os.path.isdir(sab_dir):
            return os.path.join(sab_dir, "Orbs")

        return r"C:\Windhawk\StartOrbs"

    # ------------------------------------------------------------------
    # MSSTYLES
    # ------------------------------------------------------------------

    def _apply_msstyles(self, theme_name, component, variant_name=None):
        try:
            variant = self._get_variant(component, variant_name)
            if not variant:
                return {"success": False, "message": "No msstyles variant found"}

            # Find the .theme file that pairs with this msstyles
            theme_file = None
            if "theme_file" in variant:
                theme_file = self._resolve(theme_name, variant["theme_file"])
            else:
                # Auto-detect: same base name, .theme extension
                base = os.path.splitext(variant["file"])[0]
                candidate = self._resolve(theme_name, base + ".theme")
                if candidate and os.path.exists(candidate):
                    theme_file = candidate

            if theme_file and os.path.exists(theme_file):
                # First, set the registry key so the system knows the current theme
                try:
                    with reg_open_key(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Themes",
                        writable=True,
                    ) as key:
                        reg_set_value(key, "CurrentTheme", theme_file)
                    # Broadcast WM_SETTINGCHANGE so Explorer picks up the change
                    ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "ImmersiveColorSet")
                    log.info("Applied theme via registry broadcast: %s", theme_file)
                except Exception as reg_exc:
                    log.warning("Registry theme broadcast failed, falling back to startfile: %s", reg_exc)
                    if not hasattr(os, "startfile"):
                        return {
                            "success": False,
                            "message": f"Theme file launch requires Windows: {theme_file}",
                        }
                    os.startfile(theme_file)
                    log.info("Applied theme file: %s", theme_file)
            else:
                # Fallback: set registry key directly (requires sign-out to take effect)
                full_path = self._resolve(theme_name, variant["file"])
                if full_path and os.path.exists(full_path):
                    with reg_open_key(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Themes",
                        writable=True,
                    ) as key:
                        reg_set_value(key, "CurrentTheme", full_path)
                    log.info("Set CurrentTheme registry key to: %s", full_path)
                    return {
                        "success": True,
                        "message": f"msstyles set (sign out/restart to apply): {variant['name']}",
                    }
                else:
                    return {"success": False, "message": f"msstyles file not found: {variant['file']}"}

            return {"success": True, "message": f"Applied msstyles: {variant['name']}"}
        except Exception as exc:
            log.exception("Error applying msstyles")
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # THEME FILES (.theme)
    # ------------------------------------------------------------------

    def _apply_themes(self, theme_name, component, variant_name=None):
        try:
            variant = self._get_variant(component, variant_name)
            if not variant:
                return {"success": False, "message": "No theme variant found"}

            full_path = self._resolve(theme_name, variant["file"])
            if not full_path or not os.path.exists(full_path):
                return {"success": False, "message": f"File not found: {full_path}"}

            if not hasattr(os, "startfile"):
                return {"success": False, "message": "Theme file launch requires Windows"}
            os.startfile(full_path)
            return {"success": True, "message": f"Applied theme file: {variant['name']}"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # WALLPAPER
    # ------------------------------------------------------------------

    def _apply_wallpaper(self, theme_name, component, variant_name=None):
        try:
            variant = self._get_variant(component, variant_name)
            if not variant:
                return {"success": False, "message": "No wallpaper variant found"}

            full_path = self._resolve(theme_name, variant["file"])
            if not full_path or not os.path.exists(full_path):
                return {"success": False, "message": f"File not found: {full_path}"}

            ok, msg = set_system_parameter(20, 0, full_path, 3)
            if not ok:
                return {"success": False, "message": f"Wallpaper apply failed: {msg}"}
            log.info("Wallpaper set to: %s", full_path)
            return {"success": True, "message": f"Applied wallpaper: {variant['name']}"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # CURSORS
    # ------------------------------------------------------------------

    # Per-role keyword hints used by _match_cursor_roles when canonical
    # filename matching fails. Lower-cased; matched against the filename
    # stem (extension stripped) and the full filename.
    _CURSOR_ROLE_KEYWORDS: dict[str, tuple[str, ...]] = {
        "Arrow":       ("arrow", "default", "normal", "select"),
        "Help":        ("help", "helpsel"),
        "AppStarting": ("appstarting", "working", "busy"),
        "Wait":        ("wait", "loading", "hourglass"),
        "Crosshair":   ("cross", "crosshair", "precision"),
        "IBeam":       ("ibeam", "text", "beam"),
        "NWPen":       ("nwpen", "pen"),
        "No":          ("unavail", "nodrop", "deny", "blocked", "no"),
        "SizeNS":      ("sizens", "ns"),
        "SizeWE":      ("sizewe", "ew"),
        "SizeNWSE":    ("sizenwse", "nwse"),
        "SizeNESW":    ("sizenesw", "nesw"),
        "SizeAll":     ("sizeall", "move"),
        "UpArrow":     ("uparrow", "up"),
        "Hand":        ("hand", "link", "pointer"),
    }

    def _match_cursor_roles(self, cursor_files: dict[str, str]) -> dict[str, str]:
        """Map ``{filename: abs_path}`` to ``{role: abs_path}``.

        Two-pass matcher:
          1. Canonical-name match — for each role, look up the canonical
             filename (from asset_studio.CURSOR_ROLES) by stem.
          2. Per-role keyword match — fall back to substring keywords from
             ``_CURSOR_ROLE_KEYWORDS``.

        Each file is assigned to at most one role (no reuse). Returns the
        15-entry role→path dict; roles with no match are simply absent.

        This replaces the previous alphabetical-assignment loop that
        produced an essentially random cursor scheme.
        """
        from core.asset_studio import CURSOR_ROLES

        # Build stem→path lookup for canonical matching (first-seen wins
        # on duplicate stems).
        name_to_path: dict[str, str] = {}
        for fname, fpath in cursor_files.items():
            stem = os.path.splitext(fname)[0].lower()
            if stem not in name_to_path:
                name_to_path[stem] = fpath

        assigned: dict[str, str] = {}
        used_paths: set[str] = set()

        # Pass 1: canonical filename match.
        for role, canonical in CURSOR_ROLES.items():
            canonical_stem = os.path.splitext(canonical)[0].lower()
            path = name_to_path.get(canonical_stem)
            if path and path not in used_paths:
                assigned[role] = path
                used_paths.add(path)

        # Pass 2: per-role keyword match.
        for role, keywords in self._CURSOR_ROLE_KEYWORDS.items():
            if role in assigned:
                continue
            for fname, fpath in cursor_files.items():
                if fpath in used_paths:
                    continue
                stem = os.path.splitext(fname)[0].lower()
                fname_lower = fname.lower()
                for kw in keywords:
                    if kw in stem or kw in fname_lower:
                        assigned[role] = fpath
                        used_paths.add(fpath)
                        break
                if role in assigned:
                    break

        return assigned

    def _apply_cursors(self, theme_name, component, variant_name=None):
        try:
            cursor_path = self._resolve(theme_name, component.get("path", "cursors"))
            if not cursor_path or not os.path.exists(cursor_path):
                return {"success": False, "message": f"Cursor path not found: {cursor_path}"}

            # Look for an .inf file
            inf_file = None
            for f in os.listdir(cursor_path):
                if f.lower().endswith(".inf"):
                    inf_file = os.path.join(cursor_path, f)
                    break

            if inf_file:
                # Install via setupapi — capture output and check return code
                # so silent INF failures are surfaced in the log.
                inf_result = subprocess.run(
                    ["rundll32.exe", "setupapi,InstallHinfSection", "DefaultInstall", "132", inf_file],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if inf_result.returncode != 0:
                    log.warning(
                        "Cursor INF install returned %d: %s",
                        inf_result.returncode, inf_result.stderr.strip(),
                    )
                else:
                    log.info("Cursors installed via INF: %s", inf_file)

            # Regardless of INF, also set registry keys directly for the cursor scheme.
            # This ensures the cursor scheme name is registered and persists.
            scheme_name = component.get("scheme_name", os.path.basename(cursor_path))
            cursor_reg = r"Control Panel\Cursors\Schemes"

            # Collect .cur/.ani files in the folder
            cursor_files = {}
            for f in sorted(os.listdir(cursor_path)):
                if f.lower().endswith((".cur", ".ani")):
                    cursor_files[f] = os.path.join(cursor_path, f)

            # Set the scheme in registry
            try:
                with reg_open_key(winreg.HKEY_CURRENT_USER, cursor_reg, writable=True) as key:
                    scheme_value = ",".join(sorted(cursor_files.values()))
                    reg_set_value(key, scheme_name, scheme_value)
            except Exception as exc:
                log.warning("Could not set cursor scheme registry key: %s", exc)

            # Set the active cursor scheme. Use the _match_cursor_roles matcher
            # (canonical-filename then keyword) instead of the old alphabetical
            # assignment that produced an essentially random cursor scheme.
            try:
                with reg_open_key(
                    winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", writable=True
                ) as key:
                    reg_set_value(key, "", scheme_name)
                    reg_set_value(key, "Scheme Source", 1)
                    for role, path in self._match_cursor_roles(cursor_files).items():
                        reg_set_value(key, role, path)
            except Exception as exc:
                log.warning("Could not set active cursor keys: %s", exc)

            # Broadcast change
            ok, msg = set_system_parameter(0x0057, 0, None, 2)
            if not ok:
                log.warning("Cursor broadcast failed: %s", msg)

            return {"success": True, "message": f"Cursors applied: {scheme_name}"}
        except Exception as exc:
            log.exception("Error applying cursors")
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # FONTS
    # ------------------------------------------------------------------

    def _apply_fonts(self, theme_name, component, variant_name=None):
        try:
            variants = component.get("variants", [])
            if not variants:
                return {"success": False, "message": "No font variants found"}

            # Honor the user's variant selection: if a variant_name was
            # provided, only install that font (was previously installing
            # ALL variants regardless of selection).
            if variant_name:
                selected = [v for v in variants if v.get("name") == variant_name]
                if selected:
                    variants = selected
                else:
                    log.warning(
                        "Requested font variant '%s' not in manifest; installing all", variant_name
                    )

            fonts_dest = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
            installed = []
            failed = []

            try:
                reg_key = winreg.OpenKey(
                    winreg.HKEY_LOCAL_MACHINE,
                    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
                    0,
                    winreg.KEY_WRITE,
                )
            except PermissionError:
                return {
                    "success": False,
                    "message": "Admin elevation required to install fonts. Please run as administrator.",
                }

            try:
                for variant in variants:
                    # Per-variant try/except so one failure (e.g., file in
                    # use) doesn't abort installation of the remaining fonts.
                    try:
                        src = self._resolve(theme_name, variant["file"])
                        if not src or not os.path.exists(src):
                            failed.append(variant.get("name", variant.get("file", "?")))
                            continue
                        filename = os.path.basename(src)
                        dest = os.path.join(fonts_dest, filename)
                        shutil.copy2(src, dest)
                        winreg.SetValueEx(reg_key, variant["name"], 0, winreg.REG_SZ, filename)
                        installed.append(variant["name"])
                        log.info("Installed font: %s", variant["name"])
                    except Exception as vexc:
                        log.warning("Failed to install font %s: %s", variant.get("name", "?"), vexc)
                        failed.append(variant.get("name", variant.get("file", "?")))
            finally:
                winreg.CloseKey(reg_key)

            # Notify the system about new fonts
            try:
                HWND_BROADCAST = 0xFFFF
                WM_FONTCHANGE = 0x001D
                ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0)
            except Exception as exc:
                log.debug("Font change broadcast failed: %s", exc)

            msg_parts = []
            if installed:
                msg_parts.append(f"Installed: {', '.join(installed)}")
            if failed:
                msg_parts.append(f"Failed: {', '.join(failed)}")
            return {"success": len(installed) > 0, "message": "; ".join(msg_parts)}
        except PermissionError:
            return {
                "success": False,
                "message": "Admin elevation required to install fonts. Please run as administrator.",
            }
        except Exception as exc:
            log.exception("Error applying fonts")
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # TERMINAL
    # ------------------------------------------------------------------

    def _apply_terminal(self, theme_name, component, variant_name=None):
        try:
            src = self._resolve(theme_name, component.get("schemes"))
            if not src or not os.path.exists(src):
                return {"success": False, "message": f"Terminal schemes not found: {src}"}

            # Try both Store and standalone Terminal settings paths
            terminal_paths = [
                os.path.join(
                    os.environ.get("LOCALAPPDATA", ""),
                    r"Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json",
                ),
                os.path.join(
                    os.environ.get("LOCALAPPDATA", ""),
                    r"Packages\Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe\LocalState\settings.json",
                ),
                os.path.join(
                    os.environ.get("LOCALAPPDATA", ""),
                    "Microsoft\\Windows Terminal\\settings.json",
                ),
            ]

            terminal_settings = None
            for path in terminal_paths:
                if os.path.exists(path):
                    terminal_settings = path
                    break

            if not terminal_settings:
                return {"success": False, "message": "Windows Terminal settings not found (is it installed?)"}

            # Backup original settings
            backup = terminal_settings + ".bak"
            shutil.copy2(terminal_settings, backup)

            with open(terminal_settings, "r", encoding="utf-8") as f:
                settings = json.load(f)

            with open(src, "r", encoding="utf-8") as f:
                new_schemes = json.load(f)

            # Normalize: always work with a list of schemes
            if isinstance(new_schemes, dict) and "schemes" in new_schemes:
                new_schemes = new_schemes["schemes"]

            # Merge schemes (update existing by name, add new ones)
            existing_schemes = settings.get("schemes", [])
            # Guard against malformed settings.json where schemes isn't a list.
            if not isinstance(existing_schemes, list):
                existing_schemes = []
                settings["schemes"] = existing_schemes
            # Use .get("name") so a scheme dict without a name doesn't KeyError.
            scheme_map = {s.get("name", ""): i for i, s in enumerate(existing_schemes)}

            applied_names = []
            for scheme in new_schemes:
                name = scheme.get("name", "")
                if name in scheme_map:
                    existing_schemes[scheme_map[name]] = scheme
                else:
                    existing_schemes.append(scheme)
                applied_names.append(name)

            settings["schemes"] = existing_schemes

            # Switch the default profile's color scheme to the first new scheme.
            # profiles may be a list (Terminal schema permits that) — guard.
            if applied_names and isinstance(settings.get("profiles"), dict):
                default_profile = settings["profiles"].get("defaults", {})
                default_profile["colorScheme"] = applied_names[0]
                settings["profiles"]["defaults"] = default_profile

            atomic_write_json(terminal_settings, settings, indent=4)

            log.info("Terminal schemes applied: %s", ", ".join(applied_names))
            return {
                "success": True,
                "message": f"Terminal schemes applied: {', '.join(applied_names)}",
            }
        except Exception as exc:
            log.exception("Error applying terminal")
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # FIREFOX
    # ------------------------------------------------------------------

    def _apply_firefox(self, theme_name, component, variant_name=None):
        try:
            # Use profiles.ini to find the correct profile directory
            firefox_path = os.path.join(os.environ.get("APPDATA", ""), "Mozilla", "Firefox")
            profiles_ini = os.path.join(firefox_path, "profiles.ini")

            if not os.path.exists(profiles_ini):
                return {"success": False, "message": "Firefox profiles.ini not found"}

            # Parse profiles.ini to find the default profile
            profile_dirs = []
            try:
                with open(profiles_ini, "r", encoding="utf-8") as f:
                    current_section = {}
                    for line in f:
                        line = line.strip()
                        if line.startswith("["):
                            if current_section.get("Path"):
                                profile_dirs.append(current_section)
                            current_section = {}
                        elif "=" in line:
                            key, _, value = line.partition("=")
                            current_section[key.strip()] = value.strip()
                    if current_section.get("Path"):
                        profile_dirs.append(current_section)
            except Exception as exc:
                log.warning("Could not parse profiles.ini: %s", exc)

            # Filter to default profiles
            target_profiles = []
            for prof in profile_dirs:
                is_relative = prof.get("IsRelative", "1") == "1"
                path = prof.get("Path", "")
                if not path:
                    continue
                if is_relative:
                    full_path = os.path.join(firefox_path, path)
                else:
                    full_path = path
                # Apply to all profiles, but prefer default-release
                if os.path.isdir(full_path):
                    target_profiles.append(full_path)

            if not target_profiles:
                return {"success": False, "message": "No Firefox profiles found"}

            # Find the source chrome directory
            src_chrome_path = None
            if "userChrome" in component:
                resolved = self._resolve(theme_name, component["userChrome"])
                if resolved:
                    src_chrome_path = os.path.dirname(resolved)
            elif "path" in component:
                src_chrome_path = self._resolve(theme_name, component["path"])

            if not src_chrome_path or not os.path.isdir(src_chrome_path):
                return {"success": False, "message": "Firefox chrome directory not found in theme"}

            applied_profiles = []
            for profile_dir in target_profiles:
                chrome_dir = os.path.join(profile_dir, "chrome")
                os.makedirs(chrome_dir, exist_ok=True)

                # Enable legacy stylesheets
                prefs_path = os.path.join(profile_dir, "prefs.js")
                pref_line = 'user_pref("toolkit.legacyUserProfileCustomizations.stylesheets", true);'
                if os.path.exists(prefs_path):
                    with open(prefs_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    if "toolkit.legacyUserProfileCustomizations.stylesheets" not in content:
                        with open(prefs_path, "a", encoding="utf-8") as f:
                            f.write(f"\n{pref_line}\n")

                # Copy chrome files
                for item in os.listdir(src_chrome_path):
                    s = os.path.join(src_chrome_path, item)
                    d = os.path.join(chrome_dir, item)
                    if os.path.isfile(s):
                        shutil.copy2(s, d)

                # Also write to user.js for persistence
                user_js = os.path.join(profile_dir, "user.js")
                with open(user_js, "a", encoding="utf-8") as f:
                    f.write(f"\n{pref_line}\n")

                applied_profiles.append(os.path.basename(profile_dir))

            return {
                "success": True,
                "message": f"Firefox applied to {len(applied_profiles)} profile(s)",
            }
        except Exception as exc:
            log.exception("Error applying firefox")
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # WINDHAWK
    # ------------------------------------------------------------------

    def _apply_windhawk(self, theme_name, component, variant_name=None):
        try:
            windhawk_path = os.path.join(
                os.environ.get("APPDATA", ""), "Windhawk", "ModsWritable"
            )
            if not os.path.exists(windhawk_path):
                return {"success": False, "message": "Windhawk mods directory not found"}

            mods = component.get("mods", [])
            applied = []

            if isinstance(mods, str):
                # Folder path format
                mods_folder = self._resolve(theme_name, mods)
                if not mods_folder or not os.path.isdir(mods_folder):
                    return {"success": False, "message": f"Windhawk mods folder not found: {mods_folder}"}
                for filename in os.listdir(mods_folder):
                    if filename.lower().endswith((".yaml", ".ini")):
                        src = os.path.join(mods_folder, filename)
                        dest = os.path.join(windhawk_path, filename)
                        shutil.copy2(src, dest)
                        applied.append(filename)
            elif isinstance(mods, list):
                for mod in mods:
                    src = self._resolve(theme_name, mod.get("file", ""))
                    if not src or not os.path.exists(src):
                        continue
                    filename = os.path.basename(src)
                    dest = os.path.join(windhawk_path, filename)
                    shutil.copy2(src, dest)
                    applied.append(mod.get("name", filename))

            # Attempt to signal Windhawk to reload mods. Capture stdout/stderr
            # and wait (with a short timeout) so we can report whether the
            # reload actually happened — the previous fire-and-forget Popen
            # always reported success even if Windhawk wasn't running.
            reload_msg = ""
            try:
                windhawk_exe = os.path.join(
                    os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                    "Windhawk",
                    "Windhawk.exe",
                )
                if os.path.exists(windhawk_exe):
                    proc = subprocess.Popen(
                        [windhawk_exe, "-reloadmods"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        creationflags=0x00000008,
                    )
                    try:
                        proc.wait(timeout=5)
                        reload_msg = f"; Windhawk reload signaled (pid {proc.pid}, rc={proc.returncode})"
                        log.info("Signaled Windhawk to reload mods (rc=%s)", proc.returncode)
                    except subprocess.TimeoutExpired:
                        reload_msg = f"; Windhawk reload timed out (pid {proc.pid})"
                        log.warning("Windhawk reload timed out; process may still be starting")
            except Exception as exc:
                log.debug("Could not signal Windhawk reload: %s", exc)
                reload_msg = f"; Windhawk reload skipped: {exc}"

            return {
                "success": True,
                "message": f"Windhawk mods applied: {', '.join(applied)}{reload_msg}",
            }
        except Exception as exc:
            log.exception("Error applying windhawk")
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # START ORB
    # ------------------------------------------------------------------

    def _apply_startorb(self, theme_name, component, variant_name=None):
        try:
            variant = self._get_variant(component, variant_name)
            if not variant:
                return {"success": False, "message": "No start orb variant found"}

            src = self._resolve(theme_name, variant["file"])
            if not src or not os.path.exists(src):
                return {"success": False, "message": f"Orb file not found: {src}"}

            # Route orb to the correct directory based on "target" field or auto-detection
            target = variant.get("target", component.get("target", ""))
            dest_dir = self._resolve_orb_dir(target)

            # Guard: _resolve_orb_dir may return None when neither StartAllBack
            # nor Windhawk is installed. os.makedirs(None) raises a confusing
            # TypeError — surface a clear message instead.
            if dest_dir is None:
                return {
                    "success": False,
                    "message": "Start-orb target directory not found — is StartAllBack or Windhawk installed?",
                }

            os.makedirs(dest_dir, exist_ok=True)
            dest_path = os.path.join(dest_dir, os.path.basename(src))
            shutil.copy2(src, dest_path)

            location = "StartAllBack/Orbs" if "StartAllBack" in dest_dir else "Windhawk/StartOrbs"
            return {"success": True, "message": f"Installed Start Orb to {location}: {os.path.basename(src)}"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # GUIDE-TYPE COMPONENTS (StartAllBack, MicaForEveryone, OldNewExplorer)
    # ------------------------------------------------------------------

    def _apply_startallback(self, theme_name, component, variant_name=None):
        try:
            results = []

            # Check for automated registry settings first
            settings_reg = component.get("settings_reg")
            if settings_reg:
                reg_result = self._apply_startallback_auto(theme_name, settings_reg)
                if reg_result["success"]:
                    results.append(reg_result["message"])

            # Resolve the skin to install
            skin_rel = None
            variant = self._get_variant(component, variant_name)
            if variant:
                skin_rel = variant.get("file")
            
            # Fallback to top-level "skin" key (legacy or simple manifest)
            if not skin_rel:
                skin_rel = component.get("skin")

            if skin_rel:
                skin_src = self._resolve(theme_name, skin_rel)
                if skin_src and os.path.exists(skin_src):
                    styles_dir = self._find_sab_styles_dir()
                    if styles_dir:
                        os.makedirs(styles_dir, exist_ok=True)
                        dest = os.path.join(styles_dir, os.path.basename(skin_src))
                        shutil.copy2(skin_src, dest)
                        results.append(f"Skin installed: {os.path.basename(skin_src)}")
                    else:
                        return {"success": False, "message": "StartAllBack Styles directory not found. Is StartAllBack installed?"}
                else:
                    results.append(f"Skin file not found: {skin_rel}")

            # Install orb image if referenced directly in the startallback component (legacy)
            orb_rel = component.get("orb")
            if orb_rel:
                orb_src = self._resolve(theme_name, orb_rel)
                if orb_src and os.path.exists(orb_src):
                    orbs_dir = self._find_sab_orbs_dir()
                    if orbs_dir:
                        os.makedirs(orbs_dir, exist_ok=True)
                        dest = os.path.join(orbs_dir, os.path.basename(orb_src))
                        shutil.copy2(orb_src, dest)
                        results.append(f"Orb installed: {os.path.basename(orb_src)}")
                    else:
                        results.append("StartAllBack Orbs directory not found; orb skipped")

            guide_rel = component.get("guide")
            guide_abs = self._resolve(theme_name, guide_rel) if guide_rel else None

            auto_msg = "; ".join(results) if results else "No auto-apply steps"
            return {
                "success": True,
                "message": f"StartAllBack: {auto_msg}. Open the guide for manual settings.",
                "guide": True,
                "guide_path": guide_abs,
                "app": component.get("app", "startallback"),
            }
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    def _apply_mica(self, theme_name, component, variant_name=None):
        try:
            settings_path = self._find_mica_settings_path()
            mica_json = component.get("settings_json")

            if settings_path and mica_json:
                return self._apply_mica_auto(theme_name, mica_json, settings_path)

            guide_rel = component.get("guide")
            guide_abs = self._resolve(theme_name, guide_rel) if guide_rel else None
            return {
                "success": True,
                "message": "MicaForEveryone requires manual configuration. Opening guide.",
                "guide": True,
                "guide_path": guide_abs,
                "app": component.get("app", "mica"),
            }
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    def _find_mica_settings_path(self) -> str | None:
        """Locate MicaForEveryone settings.json path."""
        local = os.environ.get("LOCALAPPDATA", "")
        mica_paths = [
            os.path.join(local, r"Packages\DongleInsovaki.MicaForEveryone_tj1q2yqf9jq8g\LocalState\settings.json"),
            os.path.join(local, r"Packages\DongleInsovaki.MicaForEveryone_*\LocalState\settings.json"),
        ]
        for pattern_path in mica_paths:
            if "*" in pattern_path:
                import glob
                matches = glob.glob(pattern_path)
                if matches:
                    return matches[0]
            elif os.path.exists(pattern_path):
                return pattern_path
        return None

    def _apply_mica_auto(self, theme_name: str, mica_json: str, settings_path: str) -> dict:
        """Apply MicaForEveryone settings from JSON file."""
        try:
            src_path = self._resolve(theme_name, mica_json)
            if not src_path or not os.path.exists(src_path):
                return {"success": False, "message": f"Mica settings file not found: {mica_json}"}

            with open(src_path, "r", encoding="utf-8") as f:
                settings = json.load(f)

            # Backup original settings
            backup = settings_path + ".bak"
            shutil.copy2(settings_path, backup)

            atomic_write_json(settings_path, settings, indent=2)

            return {
                "success": True,
                "message": f"MicaForEveryone settings applied automatically",
            }
        except PermissionError:
            return {"success": False, "message": "Admin privileges required to modify MicaForEveryone settings"}
        except Exception as exc:
            return {"success": False, "message": f"Mica auto-apply failed: {exc}"}

    def _apply_startallback_auto(self, theme_name: str, settings_reg: str) -> dict:
        """Apply StartAllBack settings from .reg file."""
        try:
            reg_path = self._resolve(theme_name, settings_reg)
            if not reg_path or not os.path.exists(reg_path):
                return {"success": False, "message": f"SAB settings file not found: {settings_reg}"}

            result = subprocess.run(
                ["reg", "import", reg_path],
                capture_output=True,
                text=True,
                creationflags=0x00000008,
            )

            if result.returncode == 0:
                return {"success": True, "message": "StartAllBack registry settings applied"}
            else:
                return {"success": False, "message": f"Reg import failed: {result.stderr}"}
        except PermissionError:
            return {"success": False, "message": "Admin privileges required for SAB registry import"}
        except Exception as exc:
            return {"success": False, "message": f"SAB auto-apply failed: {exc}"}

    def _apply_oldnewexplorer(self, theme_name, component, variant_name=None):
        try:
            guide_rel = component.get("guide")
            guide_abs = self._resolve(theme_name, guide_rel) if guide_rel else None
            return {
                "success": True,
                "message": "OldNewExplorer requires manual configuration. Opening guide.",
                "guide": True,
                "guide_path": guide_abs,
                "app": component.get("app", "oldnewexplorer"),
            }
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # RESOURCE REDIRECT
    # ------------------------------------------------------------------

    def _apply_resource_redirect(self, theme_name, component, variant_name=None):
        try:
            src_rel = component.get("path", "resource_redirect")
            src_dir = self._resolve(theme_name, src_rel)
            if not src_dir or not os.path.exists(src_dir):
                return {"success": False, "message": f"Resource redirect folder not found: {src_dir}"}

            dest_dir = os.path.join(r"C:\Windhawk", "Resources", theme_name)
            os.makedirs(dest_dir, exist_ok=True)

            copied = []
            for filename in os.listdir(src_dir):
                src_file = os.path.join(src_dir, filename)
                if os.path.isfile(src_file):
                    shutil.copy2(src_file, os.path.join(dest_dir, filename))
                    copied.append(filename)

            if copied:
                return {"success": True, "message": f"Resources copied: {', '.join(copied)}"}
            else:
                return {"success": False, "message": "No files found in resource redirect folder"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # ICONS (shortcut icons)
    # ------------------------------------------------------------------

    def _apply_icons(self, theme_name, component, variant_name=None):
        """Apply icon set to taskbar shortcuts or Windhawk Resource Redirect.

        Handles both:
        - Shortcut icons via IconSetManager (taskbar pinned shortcuts)
        - Windhawk Resource Redirect icons (system DLL replacement)
        """
        try:
            from core.asset_studio import IconSetManager
            icon_manager = IconSetManager()

            # Check for Windhawk Resource Redirect mode
            wh_resource_path = component.get("windhawk_path")
            if wh_resource_path:
                return self._apply_icons_windhawk(theme_name, component, wh_resource_path)

            variant = self._get_variant(component, variant_name)
            set_name = variant["name"] if variant else "Default"
            results = icon_manager.apply_set(set_name)
            success_count = sum(1 for r in results.values() if r["success"])
            return {
                "success": success_count > 0,
                "message": f"Icons applied: {success_count}/{len(results)} shortcuts updated",
            }
        except ImportError:
            return {"success": False, "message": "Asset studio module not available"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    def _apply_icons_windhawk(self, theme_name: str, component: dict, wh_path: str) -> dict[str, Any]:
        """Deploy icons to Windhawk Resource Redirect directory.

        Intelligently processes icon files and maps them to Windhawk-compatible
        naming convention: {dll_name}_{resource_index}.ico
        """
        from themelauncher.agents.converter import IconPackConverter

        src_dir = self._resolve(theme_name, wh_path)
        if not src_dir or not os.path.exists(src_dir):
            return {"success": False, "message": f"Windhawk icon path not found: {wh_path}"}

        icon_files = [f for f in os.listdir(src_dir) if f.lower().endswith(".ico")]
        if not icon_files:
            return {"success": False, "message": "No .ico files found in windhawk_path"}

        converter = IconPackConverter()
        mapping = converter.infer_mapping(icon_files)

        dest_dir = os.path.join(r"C:\Windhawk", "Resources", theme_name)
        os.makedirs(dest_dir, exist_ok=True)

        deployed = []
        for entry in mapping["mapped"]:
            src = os.path.join(src_dir, entry["file"])
            if os.path.exists(src):
                # Windhawk expects: {dll_name}_{resource_index}.ico
                dest_name = f"{entry['dll'].replace('.dll', '')}_{entry['index']}.ico"
                dest = os.path.join(dest_dir, dest_name)
                try:
                    shutil.copy2(src, dest)
                    deployed.append(dest_name)
                except PermissionError:
                    return {"success": False, "message": "Admin privileges required for Windhawk Resources"}
                except Exception as exc:
                    log.warning("Failed to deploy %s: %s", entry["file"], exc)

        # Copy unmapped icons as-is for manual configuration
        for fname in mapping.get("unmapped", []):
            src = os.path.join(src_dir, fname)
            dest = os.path.join(dest_dir, fname)
            if os.path.exists(src):
                try:
                    shutil.copy2(src, dest)
                    deployed.append(fname)
                except Exception as exc:
                    log.warning("Failed to copy unmapped %s: %s", fname, exc)

        return {
            "success": len(deployed) > 0,
            "message": f"Windhawk icons deployed: {len(deployed)} files",
            "deployed": deployed,
            "windhawk_dir": dest_dir,
        }

    # ------------------------------------------------------------------
    # SFC (System File Checker) - elevated background thread
    # ------------------------------------------------------------------

    def run_sfc_scan(self, on_progress=None) -> dict[str, Any]:
        """Run Windows SFC scan in background thread with progress callback.

        Provides graceful error handling for admin privilege denial.

        Returns ``{"success": ..., "message": ..., "thread_started": bool,
        "thread": Thread, "result_container": dict}``. The caller can poll
        or join ``thread`` and then read ``result_container["result"]`` to
        retrieve the actual SFC outcome (previously the result was lost in
        a local dict that the caller had no handle to).
        """

        def sfc_worker():
            try:
                if on_progress:
                    on_progress("Starting SFC scan...")

                # Check for admin privileges
                try:
                    is_admin = ctypes.windll.shell32.IsUserAnAdmin()
                except Exception:
                    is_admin = False

                if not is_admin:
                    if on_progress:
                        on_progress("Admin privileges required for SFC - running in limited mode")
                    return {
                        "success": False,
                        "message": "Admin elevation required to run SFC. Please run as administrator.",
                        "requires_admin": True,
                    }

                # Run SFC /scannow
                if on_progress:
                    on_progress("Running sfc /scannow (may take 10-15 minutes)...")

                result = subprocess.run(
                    ["sfc", "/scannow"],
                    capture_output=True,
                    text=True,
                    creationflags=0x00000008,  # CREATE_NO_WINDOW
                    timeout=900,  # 15 minute timeout
                )

                if on_progress:
                    on_progress("SFC scan complete")

                return {
                    "success": result.returncode == 0,
                    "message": f"SFC exit code: {result.returncode}",
                    "stdout": result.stdout[-2000:] if result.stdout else "",
                    "stderr": result.stderr[-2000:] if result.stderr else "",
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "message": "SFC scan timed out (15 minutes)"}
            except FileNotFoundError:
                return {"success": False, "message": "SFC tool not found - not a valid Windows installation"}
            except Exception as exc:
                return {"success": False, "message": f"SFC failed: {exc}"}

        # Run in background thread
        result_container: dict[str, Any] = {"done": False, "result": None}

        def thread_wrapper():
            result_container["result"] = sfc_worker()
            result_container["done"] = True

        t = threading.Thread(target=thread_wrapper, daemon=True)
        t.start()

        # Return immediately with thread info + result_container handle so
        # the caller can retrieve the actual SFC outcome.
        return {
            "success": True,
            "message": "SFC scan started in background thread",
            "thread_started": True,
            "thread": t,
            "result_container": result_container,
        }

    def apply_theme_with_sfc_guard(self, theme_name: str, run_sfc_first: bool = False) -> dict[str, Any]:
        """Apply theme with optional SFC integrity check in elevated thread.

        If ``run_sfc_first`` is True, runs SFC scan in a background thread and
        **waits for it to finish** before applying the theme (no race on shared
        system state — SFC modifies system files; apply_full_theme modifies the
        registry, fonts dir, etc.). If SFC fails, the theme is NOT applied and
        the SFC failure is returned to the caller.
        """
        results: dict[str, Any] = {}

        if run_sfc_first:
            sfc_result = self.run_sfc_scan()
            results["sfc_check"] = sfc_result
            thread = sfc_result.get("thread")
            result_container = sfc_result.get("result_container")
            if thread is not None and result_container is not None:
                # Join the SFC thread before applying the theme so the two
                # don't race on shared system state.
                thread.join()
                sfc_outcome = result_container.get("result")
                results["sfc_result"] = sfc_outcome
                if sfc_outcome and not sfc_outcome.get("success", False):
                    # SFC failed or reported integrity issues — abort the
                    # theme application so we don't layer a fresh theme on
                    # top of corrupted system files.
                    results["theme"] = {
                        "success": False,
                        "message": (
                            f"Theme application skipped: SFC reported issues — "
                            f"{sfc_outcome.get('message', 'unknown error')}"
                        ),
                    }
                    return results

        # Apply theme
        results["theme"] = self.apply_full_theme(theme_name)
        return results
