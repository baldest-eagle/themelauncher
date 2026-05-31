"""
Manifest parser with enhanced validation.

Validates structure, required fields, palette keys, and checks that
referenced files actually exist on disk.
"""

import json
import os
from typing import Any

from core.logger import log

REQUIRED_FIELDS = ["name", "version", "palette"]
REQUIRED_PALETTE_KEYS = ["background", "accent", "text", "inactive", "border", "active"]

# Component types the launcher knows how to apply
KNOWN_COMPONENT_TYPES = {
    "msstyles", "wallpapers", "cursors", "fonts", "terminal",
    "firefox", "windhawk", "themes", "startorb", "startallback",
    "mica", "oldnewexplorer", "resource_redirect", "icons", "basebrd",
}

# Variant-based component types (have a "variants" list)
VARIANT_COMPONENT_TYPES = {
    "msstyles", "wallpapers", "startorb", "themes", "fonts", "icons",
    "startallback",
}

# Folder-based component types (referenced by "path")
FOLDER_COMPONENT_TYPES = {
    "cursors", "windhawk", "terminal", "firefox", "resource_redirect", "basebrd",
}

# Guide-based component types (require manual setup via screenshots)
GUIDE_COMPONENT_TYPES = {
    "mica", "oldnewexplorer",
}


class ManifestParser:
    def __init__(self, theme_dir: str):
        self.theme_dir = theme_dir
        self.manifest_path = os.path.join(theme_dir, "manifest.json")

    def load(self) -> dict[str, Any]:
        """Load and validate a manifest. Returns the parsed dict with _theme_dir injected."""
        if not os.path.exists(self.manifest_path):
            raise FileNotFoundError(f"No manifest.json found in {self.theme_dir}")

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._validate(data)
        data["_theme_dir"] = self.theme_dir
        return data

    def _validate(self, data: dict) -> None:
        """Validate a manifest dict. Raises ValueError on problems."""
        # Required top-level fields
        for field in REQUIRED_FIELDS:
            if field not in data:
                raise ValueError(f"Manifest missing required field: {field}")

        # Validate version is semver-like
        version = data.get("version", "")
        if not version or not isinstance(version, str):
            raise ValueError("Manifest 'version' must be a non-empty string")
        parts = version.split(".")
        if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
            log.warning("Manifest version '%s' does not follow semver (e.g. 1.0.0)", version)

        # Palette must be a dict with the expected keys
        palette = data.get("palette", {})
        if not isinstance(palette, dict):
            raise ValueError("Manifest 'palette' must be a dict")
        for key in REQUIRED_PALETTE_KEYS:
            if key not in palette:
                log.warning("Manifest palette missing key '%s' — UI may look odd", key)
            else:
                val = palette[key]
                if not isinstance(val, str) or not val.startswith("#"):
                    log.warning("Palette key '%s' value '%s' is not a valid hex color", key, val)

        # Validate component entries
        components = data.get("components", {})
        if not isinstance(components, dict):
            raise ValueError("Manifest 'components' must be a dict")

        for comp_type, comp_data in components.items():
            if comp_type not in KNOWN_COMPONENT_TYPES:
                log.warning("Unknown component type '%s' in manifest", comp_type)

            if not isinstance(comp_data, dict):
                raise ValueError(f"Component '{comp_type}' must be a dict")

            # Variant-based components should have a "variants" list
            if comp_type in VARIANT_COMPONENT_TYPES:
                variants = comp_data.get("variants", [])
                if not isinstance(variants, list):
                    raise ValueError(f"Component '{comp_type}'.variants must be a list")
                if not variants:
                    # startallback may use legacy "skin" key instead of variants
                    if comp_type == "startallback" and comp_data.get("skin"):
                        pass  # Valid legacy format — skin will be used at apply time
                    else:
                        log.warning("Component '%s' has an empty variants list", comp_type)
                for i, v in enumerate(variants):
                    if "name" not in v:
                        raise ValueError(
                            f"Component '{comp_type}' variant[{i}] missing 'name'"
                        )
                    if "file" not in v:
                        raise ValueError(
                            f"Component '{comp_type}' variant[{i}] missing 'file'"
                        )
                    # Check referenced file exists on disk
                    file_path = os.path.join(self.theme_dir, v["file"])
                    if not os.path.exists(file_path):
                        log.warning(
                            "Component '%s' variant[%d] references missing file: %s",
                            comp_type, i, v["file"],
                        )

            # Folder-based components should have a "path" key
            elif comp_type in FOLDER_COMPONENT_TYPES:
                if "path" not in comp_data and comp_type != "terminal" and comp_type != "firefox" and comp_type != "windhawk":
                    log.warning(
                        "Folder component '%s' has no 'path' key — may fail to apply",
                        comp_type,
                    )
                else:
                    # Check referenced path exists on disk
                    path_key = comp_data.get("path", "")
                    if path_key:
                        folder_path = os.path.join(self.theme_dir, path_key)
                        if not os.path.exists(folder_path):
                            log.warning(
                                "Component '%s' references missing path: %s",
                                comp_type, path_key,
                            )

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def resolve_path(self, manifest: dict, relative_path: str) -> str:
        return os.path.join(self.theme_dir, relative_path)

    def get_preview_path(self, manifest: dict) -> str | None:
        if "preview" in manifest:
            return self.resolve_path(manifest, manifest["preview"])
        return None

    def get_palette(self, manifest: dict) -> dict:
        return manifest.get("palette", {})

    def get_component(self, manifest: dict, component_name: str) -> dict:
        return manifest.get("components", {}).get(component_name, {})