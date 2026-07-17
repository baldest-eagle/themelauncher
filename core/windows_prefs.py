"""
Windows 11 Preferences Manager.

Handles system-level settings: dark/light mode, accent color, and wallpaper display options.
"""

import ctypes
import json
import os
import shutil
import subprocess
import winreg
from typing import Any

from core.logger import log


class WindowsPrefs:
    """Manages Windows 11 system preferences."""

    WALLPAPER_STYLES = {
        "fill": 2,
        "fit": 1,
        "stretch": 257,
        "tile": 129,
        "span": 262,
    }

    @staticmethod
    def get_dark_mode() -> bool:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0
        except Exception:
            return False

    @staticmethod
    def set_dark_mode(dark: bool) -> dict[str, Any]:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                0,
                winreg.KEY_WRITE,
            )
            winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, 0 if dark else 1)
            winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, 0 if dark else 1)
            winreg.CloseKey(key)

            ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "ImmersiveColorSet")

            return {"success": True, "message": f"Dark mode {'enabled' if dark else 'disabled'}"}
        except PermissionError:
            return {"success": False, "message": "Admin privileges required for system-wide theme change"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    @staticmethod
    def get_accent_color() -> str:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Dwm",
            )
            value, _ = winreg.QueryValueEx(key, "ColorizationColor")
            winreg.CloseKey(key)
            argb = value & 0xFFFFFFFF
            r = (argb >> 16) & 0xFF
            g = (argb >> 8) & 0xFF
            b = argb & 0xFF
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return "#0078d4"

    @staticmethod
    def set_accent_color(hex_color: str) -> dict[str, Any]:
        try:
            hex_color = hex_color.lstrip("#")
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)

            argb = (255 << 24) | (r << 16) | (g << 8) | b

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\Dwm",
                0,
                winreg.KEY_WRITE,
            )
            winreg.SetValueEx(key, "ColorizationColor", 0, winreg.REG_DWORD, argb)
            winreg.SetValueEx(key, "ColorizationAfterglow", 0, winreg.REG_DWORD, argb)
            winreg.CloseKey(key)

            return {"success": True, "message": f"Accent color set to {hex_color}"}
        except PermissionError:
            return {"success": False, "message": "Admin privileges required"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}

    @staticmethod
    def set_wallpaper_slideshow(image_paths: list[str], style: str = "fill") -> dict[str, Any]:
        """Sets a collection of images as a slideshow background."""
        try:
            # For a proper slideshow, we create a temporary directory, 
            # copy selected images there, and point Windows to it.
            temp_dir = os.path.join(os.environ["TEMP"], "ThemeLauncher_Slideshow")
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            os.makedirs(temp_dir, exist_ok=True)
            
            for i, p in enumerate(image_paths):
                if os.path.exists(p):
                    shutil.copy2(p, os.path.join(temp_dir, f"wall_{i}{os.path.splitext(p)[1]}"))
            
            # Registry for Slideshow
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Wallpapers"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "SlideshowDirectory", 0, winreg.REG_SZ, temp_dir)
                winreg.SetValueEx(key, "BackgroundType", 0, winreg.REG_DWORD, 2) # 2 = Slideshow
            
            style_flag = WindowsPrefs.WALLPAPER_STYLES.get(style, 2)
            # Set the first image to trigger refresh
            ctypes.windll.user32.SystemParametersInfoW(20, 0, image_paths[0], style_flag | 3)
                
            return {"success": True, "message": f"Slideshow set with {len(image_paths)} images"}
        except Exception as exc:
            return {"success": False, "message": str(exc)}


def apply_wallpaper_with_style(image_path: str, style: str = "fill") -> dict[str, Any]:
    try:
        if not os.path.exists(image_path):
            return {"success": False, "message": f"Image not found: {image_path}"}

        style_flag = WindowsPrefs.WALLPAPER_STYLES.get(style, 2)

        result = ctypes.windll.user32.SystemParametersInfoW(20, 0, image_path, style_flag | 3)

        if result:
            log.info("Wallpaper applied with style %s: %s", style, image_path)
            return {"success": True, "message": f"Wallpaper applied ({style})"}
        else:
            return {"success": False, "message": "Failed to apply wallpaper"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}