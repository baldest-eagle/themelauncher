"""
Theme discovery, import, and state management.

Key architectural decisions:
- Constructor does NOT auto-discover; caller must call discover_themes() once.
- set_active_theme() tracks folder-type components too (not just variant-type).
- delete_theme / import_theme use incremental dict updates, not full re-scans.
"""

import copy
import json
import os
import shutil
from typing import Any

from core._io import atomic_write_json
from core.logger import log
from core.manifest_parser import (
    FOLDER_COMPONENT_TYPES,
    KNOWN_COMPONENT_TYPES,
    ManifestParser,
    VARIANT_COMPONENT_TYPES,
)


class ThemeManager:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.themes: dict[str, dict[str, Any]] = {}
        self.active_theme: str | None = self.config.get("active_theme")
        # Validate active_components schema. A malformed config (e.g., a list
        # instead of a dict, or non-string values) would crash set_active_theme
        # later with a confusing AttributeError. Coerce to dict[str, str].
        raw_ac = self.config.get("active_components", {})
        if isinstance(raw_ac, dict):
            self.active_components = {
                str(k): str(v) for k, v in raw_ac.items()
                if v is not None
            }
        else:
            log.warning(
                "config.json 'active_components' is malformed (%s); resetting to empty",
                type(raw_ac).__name__,
            )
            self.active_components = {}

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    def _load_config(self) -> dict:
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"config.json not found at {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_config(self) -> None:
        self.config["active_theme"] = self.active_theme
        self.config["active_components"] = self.active_components
        atomic_write_json(self.config_path, self.config, indent=2)

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_themes(self) -> dict[str, dict[str, Any]]:
        """Scan the themes directory and load all valid themes.

        MUST be called explicitly once after construction.
        """
        self.themes = {}
        themes_dir = self.config.get("themes_directory")
        if not themes_dir:
            raise ValueError("config.json missing 'themes_directory'")
        if not os.path.exists(themes_dir):
            os.makedirs(themes_dir, exist_ok=True)
            log.warning("Themes directory created at %s — it is empty", themes_dir)
            return self.themes

        for folder_name in os.listdir(themes_dir):
            folder_path = os.path.join(themes_dir, folder_name)
            if not os.path.isdir(folder_path):
                continue
            try:
                parser = ManifestParser(folder_path)
                manifest = parser.load()
                self.themes[manifest["name"]] = {
                    "manifest": manifest,
                    "parser": parser,
                    "path": folder_path,
                }
                log.info("Loaded theme: %s", manifest["name"])
            except (FileNotFoundError, ValueError) as exc:
                log.warning("Skipping %s: %s", folder_name, exc)

        return self.themes

    # ------------------------------------------------------------------
    # Import / Delete
    # ------------------------------------------------------------------

    def import_theme_folder(self, source_folder: str) -> dict[str, Any]:
        """Import a theme folder into the managed themes directory."""
        if not os.path.exists(source_folder) or not os.path.isdir(source_folder):
            return {"success": False, "message": "Selected folder does not exist or is not a directory."}

        themes_dir = self.config.get("themes_directory")
        if not themes_dir:
            return {"success": False, "message": "Themes directory not configured."}
        os.makedirs(themes_dir, exist_ok=True)

        folder_name = os.path.basename(os.path.normpath(source_folder))
        dest_folder = os.path.join(themes_dir, folder_name)

        # Already inside themes dir?
        if os.path.abspath(source_folder) == os.path.abspath(dest_folder):
            return {"success": False, "message": "That theme is already in your themes folder."}

        # Handle name collision
        if os.path.exists(dest_folder):
            counter = 2
            while os.path.exists(dest_folder):
                dest_folder = os.path.join(themes_dir, f"{folder_name} ({counter})")
                counter += 1

        try:
            shutil.copytree(source_folder, dest_folder)
        except Exception as exc:
            return {"success": False, "message": f"Failed to copy theme: {exc}"}

        manifest_path = os.path.join(dest_folder, "manifest.json")
        if not os.path.exists(manifest_path):
            from themelauncher.agents.manifest_generator import ManifestGenerator
            organizer = ManifestGenerator()
            result = organizer.generate(dest_folder)
            if not result.get("success"):
                return {"success": False, "message": f"Failed to generate manifest: {result.get('message', 'Unknown error')}"}

        try:
            parser = ManifestParser(dest_folder)
            manifest = parser.load()
            self.themes[manifest["name"]] = {
                "manifest": manifest,
                "parser": parser,
                "path": dest_folder,
            }
        except (FileNotFoundError, ValueError) as exc:
            log.error("Imported theme failed re-parse: %s", exc)
            return {"success": False, "message": f"Theme copied but manifest is invalid: {exc}"}

        imported_name = manifest.get("name", os.path.basename(dest_folder))
        return {
            "success": True,
            "message": f'Theme "{imported_name}" imported successfully.',
            "theme_name": imported_name,
        }

    def delete_theme(self, theme_name: str) -> dict[str, Any]:
        """Delete a theme from the managed directory and remove from the dict."""
        theme = self.themes.get(theme_name)
        if not theme:
            return {"success": False, "message": f'Theme "{theme_name}" not found.'}

        theme_path = theme.get("path")
        if not theme_path or not os.path.exists(theme_path):
            self.themes.pop(theme_name, None)
            return {"success": True, "message": f'Theme "{theme_name}" already removed from disk.'}

        # Safety: refuse to delete if themes_directory is missing/empty —
        # otherwise os.path.abspath("") resolves to CWD and the commonpath
        # guard can wrongly allow or block the delete based on CWD.
        themes_dir_raw = self.config.get("themes_directory", "")
        if not themes_dir_raw:
            return {
                "success": False,
                "message": "Themes directory not configured; refusing to delete.",
            }

        # Safety: only delete inside managed directory
        themes_dir = os.path.abspath(themes_dir_raw)
        target_path = os.path.abspath(theme_path)
        try:
            common = os.path.commonpath([themes_dir, target_path])
        except ValueError:
            return {"success": False, "message": "Refusing to delete theme outside managed directory."}
        if common != themes_dir:
            return {"success": False, "message": "Refusing to delete theme outside managed directory."}

        try:
            shutil.rmtree(target_path)
        except Exception as exc:
            return {"success": False, "message": f"Failed to delete theme folder: {exc}"}

        self.themes.pop(theme_name, None)

        if self.active_theme == theme_name:
            self.active_theme = None
            self.active_components = {}
            self._save_config()

        return {"success": True, "message": f'Theme "{theme_name}" deleted successfully.'}

    # ------------------------------------------------------------------
    # Active theme state
    # ------------------------------------------------------------------

    def set_active_theme(self, theme_name: str) -> None:
        """Set the active theme and populate active_components for ALL component types."""
        if theme_name not in self.themes:
            raise ValueError(f"Theme not found: {theme_name}")

        self.active_theme = theme_name
        self.config["active_theme"] = theme_name

        saved = self.config.get("active_components", {})
        manifest = self.themes[theme_name]["manifest"]
        components = manifest.get("components", {})

        merged: dict[str, str] = {}
        for comp_type, comp_data in components.items():
            if not isinstance(comp_data, dict):
                continue

            if comp_type in VARIANT_COMPONENT_TYPES and "variants" in comp_data:
                variants = comp_data.get("variants", [])
                if not variants:
                    continue
                first_name = variants[0]["name"]
                saved_name = saved.get(comp_type)
                valid_names = {v["name"] for v in variants}
                merged[comp_type] = saved_name if saved_name in valid_names else first_name

            elif comp_type in FOLDER_COMPONENT_TYPES:
                folder_path = comp_data.get("path", comp_type)
                merged[comp_type] = saved.get(comp_type, folder_path)

            elif comp_type in ("mica", "oldnewexplorer"):
                merged[comp_type] = saved.get(comp_type, "guide")

            elif comp_type == "startallback":
                merged[comp_type] = saved.get(comp_type, "guide")

            else:
                merged[comp_type] = saved.get(comp_type, "")

        self.active_components = merged
        self.config["active_components"] = self.active_components
        self._save_config()

    def set_active_component(self, component_type: str, variant_name: str) -> None:
        self.active_components[component_type] = variant_name
        if "active_components" not in self.config:
            self.config["active_components"] = {}
        self.config["active_components"][component_type] = variant_name
        self._save_config()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_theme(self, theme_name: str) -> dict[str, Any] | None:
        return self.themes.get(theme_name)

    def get_all_themes(self) -> dict[str, dict[str, Any]]:
        # Shallow copy so callers can't mutate our internal state.
        return dict(self.themes)

    def get_active_palette(self) -> dict[str, str]:
        if not self.active_theme:
            return self._default_palette()
        theme = self.themes.get(self.active_theme)
        if not theme:
            return self._default_palette()
        return theme["manifest"].get("palette", self._default_palette())

    def get_component_variants(self, theme_name: str, component_name: str) -> list[dict]:
        theme = self.themes.get(theme_name)
        if not theme:
            return []
        component = theme["manifest"].get("components", {}).get(component_name, {})
        return component.get("variants", [])

    def resolve_component_path(self, theme_name: str, relative_path: str) -> str | None:
        theme = self.themes.get(theme_name)
        if not theme:
            return None
        return os.path.join(theme["path"], relative_path)

    @staticmethod
    def _default_palette() -> dict[str, str]:
        return {
            "background": "#2b2b2b",
            "accent": "#3d3d3d",
            "text": "#ffffff",
            "inactive": "#1a1a1a",
            "border": "#555555",
            "active": "#ffffff",
        }