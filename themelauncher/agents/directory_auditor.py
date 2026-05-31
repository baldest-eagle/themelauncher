"""
Directory Auditor Agent (Tier 1 - Critical).

Audits theme folders for structural consistency and standardizes file extensions.
Flags missing manifest.json files for the bot-builder pipeline.
"""

import os
from typing import Any

from ..core.logger import log


REQUIRED_SUBDIRS = ["styles", "wallpaper", "source"]


class DirectoryAuditor:
    """Audit and standardize theme folder structures."""

    def __init__(self, themes_dir: str):
        self.themes_dir = themes_dir

    def audit_theme(self, theme_name: str) -> dict[str, Any]:
        """Audit a single theme folder. Returns audit report."""
        theme_path = os.path.join(self.themes_dir, theme_name)
        if not os.path.isdir(theme_path):
            return {"success": False, "message": f"Theme directory not found: {theme_path}"}

        report = {
            "theme": theme_name,
            "missing_manifest": False,
            "missing_subdirs": [],
            "uppercase_extensions": [],
            "issues": [],
        }

        # Check for manifest.json
        manifest_path = os.path.join(theme_path, "manifest.json")
        if not os.path.exists(manifest_path):
            report["missing_manifest"] = True
            report["issues"].append("missing manifest.json")

        # Check for uppercase extensions
        for root, dirs, files in os.walk(theme_path):
            for filename in files:
                ext = os.path.splitext(filename)[1]
                if ext != ext.lower():
                    report["uppercase_extensions"].append(os.path.relpath(
                        os.path.join(root, filename), theme_path
                    ))

        # Check for required subdirectories (informational, not enforced)
        for subdir in REQUIRED_SUBDIRS:
            if not os.path.isdir(os.path.join(theme_path, subdir)):
                report["missing_subdirs"].append(subdir)

        return report

    def audit_all(self) -> dict[str, Any]:
        """Audit all themes in the themes directory."""
        if not os.path.isdir(self.themes_dir):
            return {"success": False, "message": f"Themes directory not found: {self.themes_dir}"}

        results = []
        themes_needing_manifest = []

        for theme_name in os.listdir(self.themes_dir):
            theme_path = os.path.join(self.themes_dir, theme_name)
            if not os.path.isdir(theme_path):
                continue

            report = self.audit_theme(theme_name)
            results.append(report)

            if report["missing_manifest"]:
                themes_needing_manifest.append(theme_name)

        return {
            "success": True,
            "audited": len(results),
            "themes": results,
            "themes_needing_manifest": themes_needing_manifest,
        }

    def standardize_extensions(self, theme_name: str) -> dict[str, Any]:
        """Convert all file extensions to lowercase in a theme folder."""
        theme_path = os.path.join(self.themes_dir, theme_name)
        if not os.path.isdir(theme_path):
            return {"success": False, "message": f"Theme directory not found: {theme_path}"}

        standardized = []

        for root, dirs, files in os.walk(theme_path):
            for filename in files:
                ext = os.path.splitext(filename)[1]
                if ext != ext.lower():
                    old_path = os.path.join(root, filename)
                    new_name = filename.lower()
                    new_path = os.path.join(root, new_name)
                    try:
                        os.rename(old_path, new_path)
                        standardized.append(f"{filename} -> {new_name}")
                        log.info("Renamed: %s", old_path)
                    except Exception as exc:
                        log.warning("Failed to rename %s: %s", old_path, exc)

        return {
            "success": True,
            "standardized": len(standardized),
            "renamed_files": standardized,
        }

    def is_standardized(self, theme_name: str) -> bool:
        """Check if all file extensions are already lowercase."""
        theme_path = os.path.join(self.themes_dir, theme_name)
        if not os.path.isdir(theme_path):
            return False

        for root, dirs, files in os.walk(theme_path):
            for filename in files:
                ext = os.path.splitext(filename)[1]
                if ext != ext.lower():
                    return False
        return True

    def generate_standard_structure(self, theme_name: str) -> dict[str, Any]:
        """Create standard subdirectories if they don't exist."""
        theme_path = os.path.join(self.themes_dir, theme_name)
        if not os.path.isdir(theme_path):
            return {"success": False, "message": f"Theme directory not found: {theme_path}"}

        created = []
        for subdir in REQUIRED_SUBDIRS:
            subdir_path = os.path.join(theme_path, subdir)
            if not os.path.isdir(subdir_path):
                try:
                    os.makedirs(subdir_path, exist_ok=True)
                    created.append(subdir)
                    log.info("Created subdirectory: %s", subdir_path)
                except Exception as exc:
                    log.warning("Failed to create %s: %s", subdir_path, exc)

        return {
            "success": True,
            "created": created,
        }