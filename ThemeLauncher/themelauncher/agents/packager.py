"""Theme Packager and Publisher Agent (Tier 3 - Enhancement). Export & publish themes."""

import json
import os
import shutil
import zipfile
from typing import Any, Optional

from ..core.logger import log


class ThemePackager:
    """Export a theme as a distributable folder with preview, README, and proper structure."""

    def package(self, theme_name: str, output_dir: str,
                manifest: Optional[dict] = None,
                theme_path: Optional[str] = None) -> dict[str, Any]:
        """Export theme as a distributable folder."""
        if not manifest and not theme_path:
            return {"success": False, "message": "Either manifest or theme_path required"}

        dest = os.path.join(output_dir, theme_name)
        os.makedirs(dest, exist_ok=True)

        # Copy theme assets
        if theme_path and os.path.isdir(theme_path):
            for item in os.listdir(theme_path):
                s = os.path.join(theme_path, item)
                d = os.path.join(dest, item)
                if os.path.isfile(s):
                    shutil.copy2(s, d)

        # Generate README
        readme = self.generate_readme(theme_name, manifest or {})
        with open(os.path.join(dest, "README.txt"), "w", encoding="utf-8") as f:
            f.write(readme)

        # Count files
        file_count = sum(len(files) for _, _, files in os.walk(dest))

        return {"success": True, "theme": theme_name, "output": dest, "files": file_count}

    def generate_readme(self, theme_name: str, manifest: dict) -> str:
        """Create README with install instructions."""
        palette = manifest.get("palette", {})
        components = manifest.get("components", {})

        lines = [
            f"# {theme_name}",
            f"Author: {manifest.get('author', 'Unknown')}",
            f"Version: {manifest.get('version', '1.0.0')}",
            f"Description: {manifest.get('description', '')}",
            "",
            "## Palette",
        ]
        for key, val in palette.items():
            lines.append(f"- {key}: {val}")

        lines.extend(["", "## Components"])
        for comp_type in components:
            lines.append(f"- {comp_type}")

        lines.extend([
            "",
            "## Installation",
            "1. Copy this folder to your ThemeLauncher themes directory",
            "2. Restart ThemeLauncher",
            "3. Select the theme from the gallery",
            "4. Click 'Apply Theme'",
        ])

        return "\n".join(lines)

    def package_as_zip(self, theme_name: str, output_path: str,
                       manifest: Optional[dict] = None,
                       theme_path: Optional[str] = None) -> dict[str, Any]:
        """Create distributable ZIP archive."""
        result = self.package(theme_name, os.path.dirname(output_path), manifest, theme_path)
        if not result.get("success"):
            return result

        zip_path = output_path if output_path.endswith(".zip") else output_path + ".zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(result["output"]):
                for f in files:
                    file_path = os.path.join(root, f)
                    arcname = os.path.relpath(file_path, result["output"])
                    zf.write(file_path, arcname)

        return {"success": True, "output": zip_path, "size_kb": os.path.getsize(zip_path) // 1024}