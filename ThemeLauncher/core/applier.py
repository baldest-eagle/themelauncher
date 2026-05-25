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
import winreg
from typing import Any

from core.logger import log
from core.manifest_parser import GUIDE_COMPONENT_TYPES

# Semantic cursor role mapping: registry key → filename substrings to search for
CURSOR_ROLE_PATTERNS = {
    "Arrow": ["arrow", "normal", "select"],
    "Help": ["help", "question"],
    "AppStarting": ["appstarting", "appstart", "working"],
    "Wait": ["wait", "hourglass"],
    "Crosshair": ["crosshair", "cross", "precision"],
    "IBeam": ["ibeam", "text", "beam"],
    "NWPen": ["nwpen", "pen"],
    "No": ["no", "unavailable"],
    "SizeNS": ["sizens", "ns"],
    "SizeWE": ["sizewe", "we"],
    "SizeNWSE": ["sizenwse", "nwse"],
    "SizeNESW": ["sizenesw", "nesw"],
    "SizeAll": ["sizeall", "move"],
    "UpArrow": ["uparrow", "up"],
    "Hand": ["hand", "link", "pointer"],
}


def _match_cursor_to_role(role_name: str, filenames: list[str]) -> str | None:
    """Find the best-matching cursor file for a given Windows registry cursor role."""
    patterns = CURSOR_ROLE_PATTERNS.get(role_name, [role_name.lower()])
    for pattern in patterns:
        for fname in filenames:
            if pattern in fname.lower():
                return fname
    return None


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
                os.environ["WINDIR"], "Resources", "Themes", "aero.theme"
            )
            if os.path.exists(default_theme):
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes",
                    0, winreg.KEY_WRITE,
                )
                winreg.SetValueEx(key, "CurrentTheme", 0, winreg.REG_SZ, default_theme)
                winreg.CloseKey(key)
                ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "ImmersiveColorSet")
                results["msstyles"] = {"success": True, "message": "Reverted to Aero theme"}
            else:
                results["msstyles"] = {"success": False, "message": "Default aero.theme not found"}
        except Exception as exc:
            results["msstyles"] = {"success": False, "message": str(exc)}

        # 2. Restore default wallpaper
        try:
            default_wallpaper = os.path.join(
                os.environ["WINDIR"], "Web", "Wallpaper", "Windows", "img0.jpg"
            )
            if os.path.exists(default_wallpaper):
                ctypes.windll.user32.SystemParametersInfoW(20, 0, default_wallpaper, 3)
                results["wallpapers"] = {"success": True, "message": "Wallpaper reset to default"}
            else:
                results["wallpapers"] = {"success": True, "message": "Default wallpaper not found, skipped"}
        except Exception as exc:
            results["wallpapers"] = {"success": False, "message": str(exc)}

        # 3. Reset cursors
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0, winreg.KEY_WRITE
            )
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "")
            winreg.SetValueEx(key, "Scheme Source", 0, winreg.REG_DWORD, 0)
            winreg.CloseKey(key)
            ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 2)
            results["cursors"] = {"success": True, "message": "Cursors reset to system default"}
        except Exception as exc:
            results["cursors"] = {"success": False, "message": str(exc)}

        # 4. Clear start orb
        try:
            orb_dir = r"C:\Windhawk\StartOrbs"
            if os.path.isdir(orb_dir):
                for f in os.listdir(orb_dir):
                    os.remove(os.path.join(orb_dir, f))
                results["startorb"] = {"success": True, "message": "Custom start orbs removed"}
            else:
                results["startorb"] = {"success": True, "message": "No custom orb directory found"}
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
                    if os.path.isfile(fpath):
                        os.remove(fpath)
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
            firefox_path = os.path.join(os.environ["APPDATA"], "Mozilla", "Firefox")
            if os.path.isdir(firefox_path):
                cleared = 0
                for entry in os.listdir(firefox_path):
                    profile_chrome = os.path.join(firefox_path, entry, "chrome")
                    if os.path.isdir(profile_chrome):
                        for f in os.listdir(profile_chrome):
                            fpath = os.path.join(profile_chrome, f)
                            if os.path.isfile(fpath) and f.endswith((".css", ".js", ".xml")):
                                os.remove(fpath)
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
                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Themes",
                        0,
                        winreg.KEY_WRITE,
                    )
                    winreg.SetValueEx(key, "CurrentTheme", 0, winreg.REG_SZ, theme_file)
                    winreg.CloseKey(key)
                    # Broadcast WM_SETTINGCHANGE so Explorer picks up the change
                    ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "ImmersiveColorSet")
                    log.info("Applied theme via registry broadcast: %s", theme_file)
                except Exception as reg_exc:
                    log.warning("Registry theme broadcast failed, falling back to startfile: %s", reg_exc)
                    os.startfile(theme_file)
                    log.info("Applied theme file: %s", theme_file)
            else:
                # Fallback: set registry key directly (requires sign-out to take effect)
                full_path = self._resolve(theme_name, variant["file"])
                if full_path and os.path.exists(full_path):
                    key = winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion\Themes",
                        0,
                        winreg.KEY_WRITE,
                    )
                    winreg.SetValueEx(key, "CurrentTheme", 0, winreg.REG_SZ, full_path)
                    winreg.CloseKey(key)
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

            # Apply via registry broadcast (same pattern as _apply_msstyles)
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes",
                    0,
                    winreg.KEY_WRITE,
                )
                winreg.SetValueEx(key, "CurrentTheme", 0, winreg.REG_SZ, full_path)
                winreg.CloseKey(key)
                ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "ImmersiveColorSet")
                log.info("Applied theme via registry broadcast: %s", full_path)
            except Exception as reg_exc:
                log.warning("Registry broadcast failed, falling back to startfile: %s", reg_exc)
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

            ctypes.windll.user32.SystemParametersInfoW(20, 0, full_path, 3)
            log.info("Wallpaper set to: %s", full_path)
            return {"success": True, "message": f"Applied wallpaper: {variant['name']}"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # CURSORS
    # ------------------------------------------------------------------

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
                # Install via setupapi
                subprocess.run(
                    ["rundll32.exe", "setupapi,InstallHinfSection", "DefaultInstall", "132", inf_file],
                    check=False,
                )
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
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, cursor_reg, 0, winreg.KEY_WRITE)
                scheme_value = ",".join(
                    cursor_files.get(f, "") for f in sorted(cursor_files)
                )
                winreg.SetValueEx(key, scheme_name, 0, winreg.REG_SZ, scheme_value)
                winreg.CloseKey(key)
            except Exception as exc:
                log.warning("Could not set cursor scheme registry key: %s", exc)

            # Set the active cursor scheme
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0, winreg.KEY_WRITE
                )
                winreg.SetValueEx(key, "", 0, winreg.REG_SZ, scheme_name)
                winreg.SetValueEx(key, "Scheme Source", 0, winreg.REG_DWORD, 1)
                # Set individual cursor keys
                role_map = {
                    "Arrow": "Arrow",
                    "Help": "Help",
                    "AppStarting": "AppStarting",
                    "Wait": "Wait",
                    "Crosshair": "Crosshair",
                    "IBeam": "IBeam",
                    "NWPen": "NWPen",
                    "No": "No",
                    "SizeNS": "SizeNS",
                    "SizeWE": "SizeWE",
                    "SizeNWSE": "SizeNWSE",
                    "SizeNESW": "SizeNESW",
                    "SizeAll": "SizeAll",
                    "UpArrow": "UpArrow",
                    "Hand": "Hand",
                }
                # Set individual cursor keys via semantic filename matching
                cursor_filenames = sorted(cursor_files.keys())  # just filenames, not full paths
                assigned: set[str] = set()
                for role in role_map:
                    matched = _match_cursor_to_role(role, cursor_filenames)
                    if matched and matched not in assigned:
                        winreg.SetValueEx(key, role, 0, winreg.REG_SZ, cursor_files[matched])
                        assigned.add(matched)
                    elif role == "Arrow":
                        # Arrow is the default cursor — use first unassigned file as fallback
                        for fname in cursor_filenames:
                            if fname not in assigned:
                                winreg.SetValueEx(key, role, 0, winreg.REG_SZ, cursor_files[fname])
                                assigned.add(fname)
                                break
                winreg.CloseKey(key)
            except Exception as exc:
                log.warning("Could not set active cursor keys: %s", exc)

            # Broadcast change
            ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 2)

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

            fonts_dest = os.path.join(os.environ["WINDIR"], "Fonts")
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
            finally:
                winreg.CloseKey(reg_key)

            # Notify the system about new fonts
            try:
                HWND_BROADCAST = 0xFFFF
                WM_FONTCHANGE = 0x001D
                ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_FONTCHANGE, 0, 0)
            except Exception:
                pass

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
            scheme_map = {s["name"]: i for i, s in enumerate(existing_schemes)}

            applied_names = []
            for scheme in new_schemes:
                name = scheme.get("name", "")
                if name in scheme_map:
                    existing_schemes[scheme_map[name]] = scheme
                else:
                    existing_schemes.append(scheme)
                applied_names.append(name)

            settings["schemes"] = existing_schemes

            # Switch the default profile's color scheme to the first new scheme
            if applied_names and "profiles" in settings:
                default_profile = settings["profiles"].get("defaults", {})
                default_profile["colorScheme"] = applied_names[0]
                settings["profiles"]["defaults"] = default_profile

            with open(terminal_settings, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)

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
            firefox_path = os.path.join(os.environ["APPDATA"], "Mozilla", "Firefox")
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

            # Attempt to signal Windhawk to reload mods
            try:
                windhawk_exe = os.path.join(
                    os.environ.get("PROGRAMFILES", r"C:\Program Files"),
                    "Windhawk",
                    "Windhawk.exe",
                )
                if os.path.exists(windhawk_exe):
                    subprocess.Popen([windhawk_exe, "-reloadmods"], creationflags=0x00000008)
                    log.info("Signaled Windhawk to reload mods")
            except Exception as exc:
                log.debug("Could not signal Windhawk reload: %s", exc)

            return {
                "success": True,
                "message": f"Windhawk mods applied: {', '.join(applied)}",
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

            dest_dir = r"C:\Windhawk\StartOrbs"
            os.makedirs(dest_dir, exist_ok=True)

            # Use the variant's actual filename, not hardcoded "Delta.png"
            dest_path = os.path.join(dest_dir, os.path.basename(src))
            shutil.copy2(src, dest_path)

            return {"success": True, "message": f"Installed Start Orb: {os.path.basename(src)}"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    # ------------------------------------------------------------------
    # GUIDE-TYPE COMPONENTS (StartAllBack, MicaForEveryone, OldNewExplorer)
    # ------------------------------------------------------------------

    def _apply_startallback(self, theme_name, component, variant_name=None):
        try:
            results = []

            # Auto-apply the skin file if present
            skin_rel = component.get("skin")
            if skin_rel:
                skin_src = self._resolve(theme_name, skin_rel)
                if skin_src and os.path.exists(skin_src):
                    sab_dir = os.path.join(os.environ.get("APPDATA", ""), "StartIsBack")
                    os.makedirs(sab_dir, exist_ok=True)
                    dest = os.path.join(sab_dir, os.path.basename(skin_src))
                    shutil.copy2(skin_src, dest)
                    results.append(f"Skin installed: {os.path.basename(skin_src)}")

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
        """Apply icon set to taskbar shortcuts."""
        try:
            from core.asset_studio import IconSetManager
            icon_manager = IconSetManager()
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
