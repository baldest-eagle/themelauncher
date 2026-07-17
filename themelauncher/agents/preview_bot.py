"""
Preview Bot Agent — automated ingestion and preview generation for theme assets.
"""

import os
import shutil
from typing import Optional

from .preview_generator import PreviewGenerator
from ..core.logger import log

class PreviewBot:
    """Agent that handles receiving files and generating previews."""

    def __init__(self, themes_dir: str):
        self.themes_dir = themes_dir
        self.generator = PreviewGenerator()

    def ingest_file(self, file_path: str, theme_name: Optional[str] = None) -> dict:
        """Receive a .msstyles or .theme file and generate its preview."""
        if not os.path.exists(file_path):
            return {"success": False, "message": f"File not found: {file_path}"}

        ext = os.path.splitext(file_path)[1].lower()
        if ext not in (".msstyles", ".theme"):
            return {"success": False, "message": f"Unsupported file type: {ext}"}

        # Determine target theme directory
        if not theme_name:
            theme_name = os.path.splitext(os.path.basename(file_path))[0]
        
        target_dir = os.path.join(self.themes_dir, theme_name)
        os.makedirs(target_dir, exist_ok=True)

        # Copy file to theme dir
        dest_filename = os.path.basename(file_path)
        dest_path = os.path.join(target_dir, dest_filename)
        shutil.copy2(file_path, dest_path)

        # Generate preview
        preview_filename = os.path.splitext(dest_filename)[0] + "_preview.png"
        preview_path = os.path.join(target_dir, preview_filename)

        success = False
        if ext == ".msstyles":
            success = self.generator.generate_from_msstyles(dest_path, preview_path)
        else:
            success = self.generator.generate_from_theme(dest_path, preview_path)

        if success:
            log.info("Preview Bot generated preview for %s", dest_filename)
            return {
                "success": True,
                "message": f"Preview generated for {dest_filename}",
                "theme_name": theme_name,
                "preview_path": preview_path,
                "file_path": dest_path
            }
        else:
            return {"success": False, "message": "Failed to generate preview"}
