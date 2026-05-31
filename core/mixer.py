"""
Theme Mixer — build cross-theme component mixes, apply them, and save as new themes.

Bug fix: save_as_theme no longer overwrites component variants — it appends.
"""

import copy
import json
import os
import shutil
from typing import Any

from core.logger import log
from core.manifest_parser import FOLDER_COMPONENT_TYPES, VARIANT_COMPONENT_TYPES


class Mixer:
    """
    Manages a cross-theme mix: {component_type -> {theme_name, variant_name}}.
    """

    def __init__(self, theme_manager):
        self.theme_manager = theme_manager
        self.mix: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Catalog
    # ------------------------------------------------------------------

    def get_catalog(self) -> dict[str, list[dict[str, Any]]]:
        """
        Return all selectable component slots across all themes.

        Variant-based components produce one entry per variant.
        Folder-based components produce one entry per theme that has that component.
        """
        catalog: dict[str, list[dict[str, Any]]] = {}

        for theme_name, theme_data in self.theme_manager.get_all_themes().items():
            manifest = theme_data["manifest"]
            theme_path = theme_data["path"]
            components = manifest.get("components", {})

            for comp_type, comp_data in components.items():
                if comp_type not in catalog:
                    catalog[comp_type] = []

                if comp_type in VARIANT_COMPONENT_TYPES and "variants" in comp_data:
                    for variant in comp_data["variants"]:
                        entry = {
                            "theme": theme_name,
                            "variant": variant["name"],
                            "file": variant.get("file", ""),
                        }
                        preview_rel = variant.get("preview")
                        if preview_rel:
                            preview_abs = os.path.join(theme_path, preview_rel)
                            entry["preview"] = preview_abs if os.path.exists(preview_abs) else None
                        elif comp_type == "wallpapers":
                            file_abs = os.path.join(theme_path, variant.get("file", ""))
                            img_exts = {".png", ".jpg", ".jpeg", ".bmp"}
                            if any(file_abs.lower().endswith(e) for e in img_exts) and os.path.exists(file_abs):
                                entry["preview"] = file_abs
                            else:
                                entry["preview"] = None
                        else:
                            entry["preview"] = None
                        catalog[comp_type].append(entry)
                else:
                    # Folder / config / guide type — one entry per theme
                    entry = {"theme": theme_name, "variant": None}
                    if "path" in comp_data:
                        entry["path"] = os.path.join(theme_path, comp_data["path"])
                    catalog[comp_type].append(entry)

        return catalog

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def set_slot(self, comp_type: str, theme_name: str, variant_name: str | None = None) -> None:
        self.mix[comp_type] = {"theme": theme_name, "variant": variant_name}

    def clear_slot(self, comp_type: str) -> None:
        self.mix.pop(comp_type, None)

    def clear_all(self) -> None:
        self.mix = {}

    def get_slot(self, comp_type: str) -> dict[str, Any] | None:
        return self.mix.get(comp_type)

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def apply_mix(self) -> dict[str, dict[str, Any]]:
        from core.applier import Applier

        applier = Applier(self.theme_manager)
        results: dict[str, dict[str, Any]] = {}

        for comp_type, selection in self.mix.items():
            theme_name = selection["theme"]
            variant_name = selection.get("variant")
            try:
                result = applier.apply_component(theme_name, comp_type, variant_name)
                results[comp_type] = result
            except Exception as exc:
                log.exception("Error applying mix component %s", comp_type)
                results[comp_type] = {"success": False, "message": str(exc)}

        return results

    # ------------------------------------------------------------------
    # Save as Theme
    # ------------------------------------------------------------------

    def save_as_theme(self, new_name: str, description: str = "", author: str = "") -> dict[str, Any]:
        if not self.mix:
            return {"success": False, "message": "Nothing in the mix to save."}

        themes_dir = self.theme_manager.config.get("themes_directory", "")
        if not themes_dir or not os.path.exists(themes_dir):
            return {"success": False, "message": "Themes directory not configured or missing."}

        safe_name = "".join(c for c in new_name if c.isalnum() or c in " _-").strip()
        if not safe_name:
            return {"success": False, "message": "Invalid theme name."}

        dest_folder = os.path.join(themes_dir, safe_name)
        if os.path.exists(dest_folder):
            return {"success": False, "message": f'A theme named "{safe_name}" already exists.'}

        try:
            os.makedirs(dest_folder)
            manifest: dict[str, Any] = {
                "name": new_name,
                "version": "1.0.0",
                "description": description or "Custom mix created from multiple themes.",
                "author": author or "Custom",
                "palette": self._derive_palette(),
                "components": {},
            }

            for comp_type, selection in self.mix.items():
                theme_name = selection["theme"]
                variant_name = selection.get("variant")
                theme_data = self.theme_manager.get_theme(theme_name)
                if not theme_data:
                    continue

                source_theme_path = theme_data["path"]
                comp_data = theme_data["manifest"].get("components", {}).get(comp_type, {})
                comp_dest = os.path.join(dest_folder, comp_type)
                os.makedirs(comp_dest, exist_ok=True)

                if variant_name and "variants" in comp_data:
                    variant = next(
                        (v for v in comp_data["variants"] if v["name"] == variant_name),
                        None,
                    )
                    if variant:
                        src_file = os.path.join(source_theme_path, variant["file"])
                        if os.path.exists(src_file):
                            dest_file = os.path.join(comp_dest, os.path.basename(src_file))
                            shutil.copy2(src_file, dest_file)
                            rel_file = os.path.join(comp_type, os.path.basename(src_file))
                            new_variant = {"name": variant["name"], "file": rel_file}

                            if variant.get("preview"):
                                src_preview = os.path.join(source_theme_path, variant["preview"])
                                if os.path.exists(src_preview):
                                    preview_dest = os.path.join(comp_dest, os.path.basename(src_preview))
                                    shutil.copy2(src_preview, preview_dest)
                                    new_variant["preview"] = os.path.join(comp_type, os.path.basename(src_preview))

                            # FIX: append to existing variants list instead of overwriting
                            if comp_type not in manifest["components"]:
                                manifest["components"][comp_type] = {"variants": []}
                            manifest["components"][comp_type]["variants"].append(new_variant)

                elif "path" in comp_data:
                    src_dir = os.path.join(source_theme_path, comp_data["path"])
                    if os.path.exists(src_dir):
                        shutil.copytree(src_dir, comp_dest, dirs_exist_ok=True)
                        manifest["components"][comp_type] = {"path": comp_type}

                else:
                    # Guide-type or other — copy the reference
                    manifest["components"][comp_type] = copy.deepcopy(comp_data)

            # Write manifest
            manifest_path = os.path.join(dest_folder, "manifest.json")
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)

            # Incremental add to theme manager
            try:
                from core.manifest_parser import ManifestParser
                parser = ManifestParser(dest_folder)
                loaded_manifest = parser.load()
                self.theme_manager.themes[loaded_manifest["name"]] = {
                    "manifest": loaded_manifest,
                    "parser": parser,
                    "path": dest_folder,
                }
            except Exception as exc:
                log.error("Saved theme failed re-parse: %s", exc)

            return {
                "success": True,
                "message": f'Theme "{new_name}" saved successfully.',
                "theme_name": safe_name,
            }

        except Exception as exc:
            if os.path.exists(dest_folder):
                shutil.rmtree(dest_folder, ignore_errors=True)
            log.exception("Failed to save mix as theme")
            return {"success": False, "message": f"Failed to save theme: {exc}"}

    def _derive_palette(self) -> dict[str, str]:
        msstyles_slot = self.mix.get("msstyles")
        if msstyles_slot:
            theme = self.theme_manager.get_theme(msstyles_slot["theme"])
            if theme:
                return theme["manifest"].get("palette", self._default_palette())
        return self._default_palette()

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