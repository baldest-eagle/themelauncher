"""
Asset Studio — icon set management, cursor set management, and recolouring engine.

Fixes over original:
- _DEFAULT_ICON_SETS is deep-copied on load (no mutation of global defaults)
- Paths use os.environ / dynamic resolution instead of hardcoded user paths
- recolour_image handles near-transparent pixels better
"""

import colorsys
import copy
import json
import os
import shutil
import subprocess
import winreg
from typing import Any

import numpy as np
from PIL import Image

from core.logger import log

# ---------------------------------------------------------------------------
# PATHS — all dynamically resolved
# ---------------------------------------------------------------------------

_EXTRAS_DIR = os.path.join(os.path.dirname(__file__), "..", "themes", "extras")
ICON_SETS_JSON = os.path.join(_EXTRAS_DIR, "icon_sets.json")
CURSORS_OUT_DIR = os.path.join(_EXTRAS_DIR, "cursors")
ICONS_OUT_DIR = _EXTRAS_DIR
TASKBAR_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    r"Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar",
)

# Cursor role -> canonical filename
CURSOR_ROLES = {
    "Arrow": "arrow.cur",
    "Help": "helpsel.cur",
    "AppStarting": "busy.ani",
    "Wait": "wait.ani",
    "Crosshair": "cross.cur",
    "IBeam": "ibeam.cur",
    "NWPen": "pen.cur",
    "No": "unavail.cur",
    "SizeNS": "ns.cur",
    "SizeWE": "ew.cur",
    "SizeNWSE": "nwse.cur",
    "SizeNESW": "nesw.cur",
    "SizeAll": "move.cur",
    "UpArrow": "up.cur",
    "Hand": "link.cur",
}

CURSOR_REG_KEY = r"Control Panel\Cursors"

# ---------------------------------------------------------------------------
# Draw functions for icon generation
# ---------------------------------------------------------------------------

DRAW_FUNCTIONS: dict[str, Any] = {}


def _register_draw(name: str):
    def decorator(fn):
        DRAW_FUNCTIONS[name] = fn
        return fn
    return decorator


@_register_draw("firefox")
def _draw_firefox(draw, size, color):
    c = size // 2
    draw.ellipse([10, 10, size - 10, size - 10], outline=color, width=50)
    draw.pieslice([35, 35, size - 35, size - 35], 0, 270, fill=color)


@_register_draw("explorer")
def _draw_explorer(draw, size, color):
    draw.rectangle([10, 60, size - 10, size - 30], fill=color)
    draw.rectangle([10, 20, 110, 60], fill=color)


@_register_draw("spotify")
def _draw_spotify(draw, size, color):
    c = size // 2
    for i, r in enumerate([115, 80, 45]):
        draw.arc([c - r, c - r + i * 12, c + r, c + r + i * 12], 210, 330, fill=color, width=48)


@_register_draw("gemini")
def _draw_gemini(draw, size, color):
    c, s, inner = size // 2, 120, 45
    pts = [(c, c-s), (c+inner, c-inner), (c+s, c), (c+inner, c+inner),
           (c, c+s), (c-inner, c+inner), (c-s, c), (c-inner, c-inner)]
    draw.polygon(pts, fill=color)


@_register_draw("comet")
def _draw_comet(draw, size, color):
    draw.ellipse([15, 90, 170, 245], fill=color)
    draw.polygon([(150, 110), (250, 10), (190, 190)], fill=color)


@_register_draw("warp")
def _draw_warp(draw, size, color):
    t = 30
    draw.line([70, 70, 160, 128], fill=color, width=t)
    draw.line([160, 128, 70, 186], fill=color, width=t)
    draw.line([180, 186, 230, 186], fill=color, width=t)


@_register_draw("flow")
def _draw_flow(draw, size, color):
    draw.ellipse([40, 40, 180, 180], outline=color, width=35)
    draw.line([165, 165, 230, 230], fill=color, width=40)
    draw.line([30, 220, 100, 220], fill=color, width=20)


@_register_draw("everything")
def _draw_everything(draw, size, color):
    draw.ellipse([60, 60, 160, 160], outline=color, width=20)
    draw.line([150, 150, 210, 210], fill=color, width=25)


@_register_draw("dragons")
def _draw_dragons(draw, size, color):
    draw.polygon([(80, 80), (180, 100), (100, 180)], fill=color)
    draw.arc([40, 40, 220, 220], 30, 270, fill=color, width=30)
    draw.polygon([(170, 50), (190, 80), (160, 90)], fill=color)


# ---------------------------------------------------------------------------
# Recolour engine
# ---------------------------------------------------------------------------

def recolour_image(img: Image.Image, new_hex: str) -> Image.Image:
    """Replace hue/saturation of visible pixels with new_hex, preserving luminance and alpha."""
    r_new = int(new_hex[1:3], 16) / 255.0
    g_new = int(new_hex[3:5], 16) / 255.0
    b_new = int(new_hex[5:7], 16) / 255.0
    h_new, s_new, _ = colorsys.rgb_to_hsv(r_new, g_new, b_new)

    rgba = img.convert("RGBA")
    arr = np.array(rgba, dtype=np.float32) / 255.0
    alpha = arr[:, :, 3]

    # Only recolour pixels that are sufficiently opaque
    mask = alpha > 0.05

    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    v = max_c

    h_arr = np.full_like(v, h_new)
    s_arr = np.full_like(v, s_new)

    i = (h_arr * 6.0).astype(int) % 6
    f = h_arr * 6.0 - np.floor(h_arr * 6.0)
    p = v * (1 - s_arr)
    q = v * (1 - f * s_arr)
    t_v = v * (1 - (1 - f) * s_arr)

    r_out = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [v, q, p, p, t_v, v])
    g_out = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [t_v, v, v, q, p, p])
    b_out = np.select([i == 0, i == 1, i == 2, i == 3, i == 4, i == 5], [p, p, t_v, v, v, q])

    out = arr.copy()
    out[:, :, 0] = np.where(mask, r_out, r)
    out[:, :, 1] = np.where(mask, g_out, g)
    out[:, :, 2] = np.where(mask, b_out, b)

    return Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8), "RGBA")


def recolour_ico(src_path: str, dest_path: str, new_hex: str) -> None:
    img = Image.open(src_path)
    frames = []
    n = getattr(img, "n_frames", 1)
    for i in range(n):
        img.seek(i)
        frames.append(recolour_image(img.convert("RGBA"), new_hex))
    sizes = [(f.width, f.height) for f in frames]
    frames[0].save(dest_path, format="ICO", append_images=frames[1:], sizes=sizes)


def recolour_cur(src_path: str, dest_path: str, new_hex: str) -> None:
    try:
        recolour_ico(src_path, dest_path, new_hex)
    except Exception:
        shutil.copy2(src_path, dest_path)


# ---------------------------------------------------------------------------
# Icon generation
# ---------------------------------------------------------------------------

_ICO_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]


def generate_icon(app_key: str, fg_color: str, bg_color: str = None,
                  style: str = "circle", output_path: str = None) -> str:
    draw_fn = DRAW_FUNCTIONS.get(app_key.lower(), _draw_gemini)
    size = 256
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    from PIL import ImageDraw
    draw = ImageDraw.Draw(img)

    if style == "circle" and bg_color:
        margin = 20
        draw.ellipse([margin, margin, size - margin, size - margin], fill=bg_color)

    draw_fn(draw, size, fg_color)

    if output_path is None:
        suffix = "" if style == "circle" else "_bold"
        output_path = os.path.join(ICONS_OUT_DIR, f"{app_key}{suffix}.ico")

    img.save(output_path, format="ICO", sizes=_ICO_SIZES)
    return output_path


# ---------------------------------------------------------------------------
# Default icon sets catalog — no hardcoded user paths
# ---------------------------------------------------------------------------

_DEFAULT_ICON_SETS: dict[str, Any] = {
    "sets": {
        "Japan 26": {
            "firefox": "japan26_firefox.ico", "explorer": "japan26_explorer.ico",
            "spotify": "japan26_spotify.ico", "gemini": "japan26_gemini.ico",
            "comet": "japan26_comet.ico", "warp": "japan26_warp.ico",
            "flow": "japan26_flow.ico", "everything": "japan26_everything.ico",
            "dragons": "japan26_dragons.ico",
        },
        "Japan 26 Bold": {
            "firefox": "japan26_firefox_bold.ico", "spotify": "japan26_spotify_bold.ico",
            "warp": "japan26_warp_bold.ico", "flow": "japan26_flow_bold.ico",
        },
        "Amber": {
            "firefox": "amber_firefox.ico", "explorer": "amber_explorer.ico",
            "spotify": "amber_spotify.ico", "gemini": "amber_gemini.ico",
            "comet": "amber_comet.ico",
        },
        "Amber Pro": {
            "firefox": "amber_firefox_pro.ico", "explorer": "amber_explorer_pro.ico",
            "spotify": "amber_spotify_pro.ico", "gemini": "amber_gemini_pro.ico",
            "comet": "amber_comet_pro.ico",
        },
        "Bold Amber": {
            "firefox": "bold_amber_firefox.ico", "explorer": "bold_amber_explorer.ico",
            "spotify": "bold_amber_spotify.ico", "gemini": "bold_amber_gemini.ico",
        },
        "Bold Olive": {
            "firefox": "bold_olive_firefox.ico", "explorer": "bold_olive_explorer.ico",
            "spotify": "bold_olive_spotify.ico", "gemini": "bold_olive_gemini.ico",
        },
        "Kanagawa": {
            "firefox": "firefox.ico", "explorer": "explorer.ico",
            "spotify": "spotify.ico", "gemini": "gemini.ico",
            "comet": "comet.ico", "warp": "warp.ico",
        },
        "Kanagawa Bold": {
            "firefox": "firefox_bold.ico", "explorer": "explorer_bold.ico",
            "spotify": "spotify_bold.ico", "gemini": "gemini_bold.ico",
            "comet": "comet_bold.ico", "warp": "warp_bold.ico",
        },
    },
    "apps": {
        "firefox": {
            "label": "Firefox",
            "lnk": "Firefox.lnk",
            "exe": r"C:\Program Files\Mozilla Firefox\firefox.exe",
            "draw": "firefox",
        },
        "explorer": {
            "label": "File Explorer",
            "lnk": "File Explorer.lnk",
            "exe": "",
            "draw": "explorer",
        },
        "spotify": {
            "label": "Spotify",
            "lnk": "Spotify.lnk",
            # Dynamic path instead of hardcoded kyleh
            "exe": os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
            "draw": "spotify",
        },
        "gemini": {
            "label": "Google Gemini",
            "lnk": "Google Gemini.lnk",
            "exe": r"C:\Program Files\FirefoxPWA\firefoxpwa.exe",
            "draw": "gemini",
        },
        "comet": {"label": "Comet", "lnk": "Comet.lnk", "exe": "", "draw": "comet"},
        "warp": {"label": "Warp", "lnk": "Warp.lnk", "exe": "", "draw": "warp"},
        "flow": {"label": "Flow Launcher", "lnk": "Flow Launcher.lnk", "exe": "", "draw": "flow"},
        "everything": {
            "label": "Everything",
            "lnk": "Everything.lnk",
            "exe": r"C:\Program Files\Everything\Everything.exe",
            "draw": "everything",
        },
        "dragons": {"label": "Call of Dragons", "lnk": "Call of Dragons.lnk", "exe": "", "draw": "dragons"},
    },
}


class IconSetManager:
    """Manages icon sets, app slots, custom mixes, and shortcut application."""

    def __init__(self):
        os.makedirs(_EXTRAS_DIR, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        if os.path.exists(ICON_SETS_JSON):
            with open(ICON_SETS_JSON, "r", encoding="utf-8") as f:
                return json.load(f)
        # DEEP COPY to avoid mutating the module-level default
        return copy.deepcopy(_DEFAULT_ICON_SETS)

    def _save(self) -> None:
        os.makedirs(os.path.dirname(ICON_SETS_JSON), exist_ok=True)
        with open(ICON_SETS_JSON, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    # -- Queries ------------------------------------------------------------

    def get_sets(self) -> dict:
        return self.data.get("sets", {})

    def get_apps(self) -> dict:
        return self.data.get("apps", {})

    def get_set(self, set_name: str) -> dict:
        return self.data["sets"].get(set_name, {})

    def get_set_contents(self, set_name: str) -> dict:
        """Return the {app_key: ico_filename} mapping for a set."""
        return self.data["sets"].get(set_name, {})

    def get_all_icons_for_app(self, app_key: str) -> list[dict]:
        results = []
        for set_name, icons in self.data["sets"].items():
            if app_key in icons:
                ico = icons[app_key]
                abs_path = os.path.join(_EXTRAS_DIR, ico)
                results.append({"set": set_name, "file": ico, "path": abs_path if os.path.exists(abs_path) else None})
        return results

    def get_icons_for_app(self, set_name: str, app_key: str) -> list[tuple[str, str]]:
        """Return [(ico_filename, abs_path)] for an app in a specific set."""
        icons = self.data["sets"].get(set_name, {})
        if app_key in icons:
            ico = icons[app_key]
            return [(ico, os.path.join(_EXTRAS_DIR, ico))]
        return []

    def resolve_icon_path(self, set_name: str, app_key: str, ico_file: str) -> str:
        return os.path.join(_EXTRAS_DIR, ico_file)

    # -- Mutations ----------------------------------------------------------

    def create_set(self, set_name: str, base_set: str = None) -> dict:
        if set_name in self.data["sets"]:
            raise ValueError(f'Set "{set_name}" already exists')
        base = dict(self.data["sets"].get(base_set, {})) if base_set else {}
        self.data["sets"][set_name] = base
        self._save()
        return base

    def set_slot(self, set_name: str, app_key: str, ico_filename: str) -> None:
        if set_name not in self.data["sets"]:
            self.data["sets"][set_name] = {}
        self.data["sets"][set_name][app_key] = ico_filename
        self._save()

    def delete_set(self, set_name: str) -> None:
        self.data["sets"].pop(set_name, None)
        self._save()

    def add_app(self, data_or_key, label: str = "", lnk: str = "", exe: str = "", draw: str = "") -> None:
        """Register a new app slot. Accepts either a dict or individual params."""
        if isinstance(data_or_key, dict):
            key = data_or_key.get("key", "")
            self.data["apps"][key] = {
                "label": data_or_key.get("label", ""),
                "lnk": data_or_key.get("lnk", ""),
                "exe": data_or_key.get("exe", ""),
                "draw": data_or_key.get("draw_style", data_or_key.get("draw", "")),
            }
        else:
            self.data["apps"][data_or_key] = {"label": label, "lnk": lnk, "exe": exe, "draw": draw}
        self._save()

    def remove_app(self, app_key: str) -> None:
        self.data["apps"].pop(app_key, None)
        for s in self.data["sets"].values():
            s.pop(app_key, None)
        self._save()

    def save_mixed_as_set(self, set_name: str, mix: dict) -> None:
        self.data["sets"][set_name] = dict(mix)
        self._save()

    def generate_icon(self, set_name: str, app_key: str, hex_val: str, draw_fn=None) -> None:
        """Generate an icon and add it to the set."""
        output = generate_icon(app_key, hex_val, style="bold")
        self.data["sets"][set_name][app_key] = os.path.basename(output)
        self._save()

    # -- Recolour ------------------------------------------------------------

    def recolour_set(self, source_set: str, new_hex: str, new_set_name: str = None) -> dict:
        source = self.data["sets"].get(source_set, {})
        if not source:
            raise ValueError(f'Source set "{source_set}" not found or empty')

        target_name = new_set_name or f"{source_set} (recoloured)"
        new_set = {}
        for app_key, ico_file in source.items():
            src_path = os.path.join(_EXTRAS_DIR, ico_file)
            if not os.path.exists(src_path):
                continue
            hex_tag = new_hex.lstrip("#").lower()
            new_filename = f"{os.path.splitext(ico_file)[0]}_{hex_tag}.ico"
            dest_path = os.path.join(_EXTRAS_DIR, new_filename)
            recolour_ico(src_path, dest_path, new_hex)
            new_set[app_key] = new_filename

        self.data["sets"][target_name] = new_set
        self._save()
        return new_set

    def recolour_slot(self, set_name: str, app_key: str, new_hex: str) -> str:
        ico_file = self.data["sets"].get(set_name, {}).get(app_key)
        if not ico_file:
            raise ValueError(f'No icon for "{app_key}" in set "{set_name}"')
        src_path = os.path.join(_EXTRAS_DIR, ico_file)
        if not os.path.exists(src_path):
            raise FileNotFoundError(src_path)
        hex_tag = new_hex.lstrip("#").lower()
        new_filename = f"{os.path.splitext(ico_file)[0]}_{hex_tag}.ico"
        dest_path = os.path.join(_EXTRAS_DIR, new_filename)
        recolour_ico(src_path, dest_path, new_hex)
        self.data["sets"][set_name][app_key] = new_filename
        self._save()
        return new_filename

    # -- Apply shortcuts -----------------------------------------------------

    def apply_set(self, set_name: str) -> dict:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        icon_set = self.data["sets"].get(set_name, {})
        apps = self.data["apps"]
        results = {}

        for app_key, ico_file in icon_set.items():
            app = apps.get(app_key)
            if not app:
                continue
            lnk_path = os.path.join(TASKBAR_DIR, app["lnk"])
            ico_path = os.path.join(_EXTRAS_DIR, ico_file)

            if not os.path.exists(ico_path):
                results[app_key] = {"success": False, "message": f"Icon not found: {ico_path}"}
                continue

            try:
                if not os.path.exists(lnk_path):
                    shortcut = shell.CreateShortcut(lnk_path)
                    exe = app.get("exe", "")
                    if exe:
                        shortcut.TargetPath = exe
                else:
                    shortcut = shell.CreateShortcut(lnk_path)
                shortcut.IconLocation = f"{ico_path},0"
                shortcut.Save()
                results[app_key] = {"success": True, "message": f"Applied {ico_file}"}
            except Exception as exc:
                results[app_key] = {"success": False, "message": str(exc)}

        self._notify_icon_cache()
        return results

    def apply_mixed(self, mix: dict) -> dict:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        apps = self.data["apps"]
        results = {}

        for app_key, ico_file in mix.items():
            app = apps.get(app_key)
            if not app:
                continue
            lnk_path = os.path.join(TASKBAR_DIR, app["lnk"])
            ico_path = os.path.join(_EXTRAS_DIR, ico_file)

            if not os.path.exists(ico_path):
                results[app_key] = {"success": False, "message": f"Icon not found: {ico_path}"}
                continue
            try:
                shortcut = shell.CreateShortcut(lnk_path)
                shortcut.IconLocation = f"{ico_path},0"
                shortcut.Save()
                results[app_key] = {"success": True, "message": f"Applied {ico_file}"}
            except Exception as exc:
                results[app_key] = {"success": False, "message": str(exc)}

        self._notify_icon_cache()
        return results

    @staticmethod
    def _notify_icon_cache() -> None:
        try:
            import ctypes
            ctypes.windll.shell32.SHChangeNotify(0x8000000, 0x1000, None, None)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Cursor Set Manager
# ---------------------------------------------------------------------------

class CursorSetManager:
    """Manages cursor sets sourced from theme folders and custom mixes."""

    def __init__(self, theme_manager):
        self.theme_manager = theme_manager
        os.makedirs(CURSORS_OUT_DIR, exist_ok=True)

    def get_all_sets(self) -> dict[str, dict[str, str]]:
        """Return {set_name: {role: abs_path}} for all known cursor sets."""
        sets: dict[str, dict[str, str]] = {}

        for theme_name, theme_data in self.theme_manager.get_all_themes().items():
            theme_path = theme_data["path"]
            manifest = theme_data["manifest"]
            cursor_comp = manifest.get("components", {}).get("cursors")
            if not cursor_comp:
                continue

            cursor_path = os.path.join(theme_path, cursor_comp.get("path", "cursors"))
            if not os.path.isdir(cursor_path):
                continue

            subdirs = [d for d in os.listdir(cursor_path) if os.path.isdir(os.path.join(cursor_path, d))]

            if subdirs:
                for sub in subdirs:
                    role_map = self._map_roles(os.path.join(cursor_path, sub))
                    if role_map:
                        sets[f"{theme_name} - {sub}"] = role_map
            else:
                role_map = self._map_roles(cursor_path)
                if role_map:
                    sets[theme_name] = role_map

        # Custom saved sets
        if os.path.isdir(CURSORS_OUT_DIR):
            for entry in os.listdir(CURSORS_OUT_DIR):
                entry_path = os.path.join(CURSORS_OUT_DIR, entry)
                if os.path.isdir(entry_path):
                    role_map = self._map_roles(entry_path)
                    if role_map:
                        sets[f"Custom: {entry}"] = role_map

        return sets

    def _map_roles(self, folder: str) -> dict[str, str]:
        result = {}
        for role, filename in CURSOR_ROLES.items():
            full = os.path.join(folder, filename)
            if os.path.exists(full):
                result[role] = full
        return result

    def get_cursor_for_role(self, set_name: str, role: str) -> str | None:
        """Return the path for a specific cursor role in a set."""
        all_sets = self.get_all_sets()
        role_map = all_sets.get(set_name, {})
        return role_map.get(role)

    def recolour_set(self, source_set_name: str, new_set_name: str, new_hex: str) -> dict[str, str]:
        all_sets = self.get_all_sets()
        source = all_sets.get(source_set_name)
        if not source:
            raise ValueError(f'Cursor set "{source_set_name}" not found')

        dest_dir = os.path.join(CURSORS_OUT_DIR, new_set_name)
        os.makedirs(dest_dir, exist_ok=True)
        new_map = {}

        for role, src_path in source.items():
            filename = CURSOR_ROLES[role]
            dest_path = os.path.join(dest_dir, filename)
            recolour_cur(src_path, dest_path, new_hex)
            new_map[role] = dest_path

        return new_map

    def save_mix(self, set_name: str, mix: dict[str, str]) -> str:
        dest_dir = os.path.join(CURSORS_OUT_DIR, set_name)
        os.makedirs(dest_dir, exist_ok=True)

        for role, src_path in mix.items():
            filename = CURSOR_ROLES.get(role)
            if not filename or not os.path.exists(src_path):
                continue
            shutil.copy2(src_path, os.path.join(dest_dir, filename))

        return dest_dir

    def apply_set(self, role_map: dict[str, str]) -> dict[str, dict[str, str]]:
        results = {}
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, CURSOR_REG_KEY, 0, winreg.KEY_WRITE)
        except Exception as exc:
            return {"all": {"success": False, "message": str(exc)}}

        for role, path in role_map.items():
            try:
                winreg.SetValueEx(key, role, 0, winreg.REG_SZ, path)
                results[role] = {"success": True, "message": f"Set {role}"}
            except Exception as exc:
                results[role] = {"success": False, "message": str(exc)}

        winreg.CloseKey(key)

        try:
            import ctypes
            ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 2)
        except Exception:
            pass

        return results