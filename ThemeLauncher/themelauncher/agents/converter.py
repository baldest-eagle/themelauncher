"""Icon Pack Converter Agent (Tier 2 - High Value). Convert ICO folders to 7tsp packages."""

import json
import os
from typing import Any, Optional

from ..core.logger import log

# Built-in mapping: icon filename -> (DLL, resource_index)
_DEFAULT_MAPPING: dict[str, tuple[str, int]] = {
    "computer.ico": ("imageres.dll", 109),
    "folder.ico": ("imageres.dll", 3),
    "network.ico": ("imageres.dll", 25),
    "recycle.ico": ("imageres.dll", 31),
    "recycle_full.ico": ("imageres.dll", 32),
    "drive.ico": ("imageres.dll", 8),
    "dvd.ico": ("imageres.dll", 12),
    "file.ico": ("imageres.dll", 1),
    "search.ico": ("imageres.dll", 23),
    "settings.ico": ("imageres.dll", 20),
    "user.ico": ("imageres.dll", 17),
    "library.ico": ("imageres.dll", 4),
    "download.ico": ("imageres.dll", 180),
    "music.ico": ("imageres.dll", 108),
    "picture.ico": ("imageres.dll", 113),
    "video.ico": ("imageres.dll", 115),
}


class IconPackConverter:
    """Transform raw icon packs into 7tsp-compatible packages."""

    def __init__(self):
        self._mapping = dict(_DEFAULT_MAPPING)

    def convert(self, icon_pack_path: str, output_path: str,
                pack_name: Optional[str] = None, author: Optional[str] = None) -> dict[str, Any]:
        """Full conversion pipeline: map icons, generate INI, package as 7z."""
        if not os.path.isdir(icon_pack_path):
            return {"success": False, "message": f"Directory not found: {icon_pack_path}"}

        # Map icons to resources
        mapping_result = self.map_icons_to_resources(icon_pack_path)
        if not mapping_result["mapped"]:
            return {"success": False, "message": "No icons could be mapped to known resources"}

        # Generate INI
        ini_path = os.path.join(output_path, "config.ini") if os.path.isdir(output_path) else \
            os.path.join(os.path.dirname(output_path), "config.ini")
        os.makedirs(os.path.dirname(ini_path), exist_ok=True)
        ini_content = self.generate_ini(mapping_result["mapping"], pack_name or "Icon Pack")
        with open(ini_path, "w", encoding="utf-8") as f:
            f.write(ini_content)

        # Try to package as 7z
        package_result = self.package_7z(ini_path, output_path)
        if package_result["success"]:
            return {
                "success": True,
                "mapped": len(mapping_result["mapped"]),
                "unmapped": len(mapping_result["unmapped"]),
                "output": package_result.get("output"),
            }

        return {
            "success": True,
            "mapped": len(mapping_result["mapped"]),
            "unmapped": len(mapping_result["unmapped"]),
            "ini_path": ini_path,
            "message": "INI generated; 7z packaging requires py7zr",
        }

    def map_icons_to_resources(self, ico_dir: str) -> dict[str, Any]:
        """Match filenames to DLL resource indices."""
        mapped = []
        unmapped = []
        for fname in os.listdir(ico_dir):
            if not fname.lower().endswith(".ico"):
                continue
            entry = self._mapping.get(fname.lower())
            if entry:
                mapped.append({"file": fname, "dll": entry[0], "index": entry[1]})
            else:
                unmapped.append(fname)
        return {"mapped": mapped, "unmapped": unmapped}

    def generate_ini(self, mapping: list[dict], pack_name: str) -> str:
        """Write the 7tsp INI configuration."""
        lines = ["[General]", f"Name={pack_name}", f"Author=ThemeLauncher SDK",
                 f"Description=Converted icon pack", "", "[Icons]"]
        for entry in mapping:
            lines.append(f"{entry['dll']},{entry['index']}={entry['file']}")
        return "\n".join(lines)

    def package_7z(self, ini_path: str, output_path: str) -> dict[str, Any]:
        """Create the 7z archive using py7zr if available."""
        try:
            import py7zr
            archive_path = output_path if output_path.endswith(".7z") else output_path + ".7z"
            with py7zr.SevenZipFile(archive_path, 'w') as archive:
                archive.write(ini_path, os.path.basename(ini_path))
            return {"success": True, "output": archive_path}
        except ImportError:
            log.warning("py7zr not available; cannot create 7z package")
            return {"success": False, "message": "py7zr not installed"}

    def add_custom_mapping(self, filename: str, dll: str, index: int) -> None:
        """Extend the built-in mapping table."""
        self._mapping[filename.lower()] = (dll, index)