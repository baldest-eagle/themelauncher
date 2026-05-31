"""
Manifest Auto-Generator Agent (Tier 1 - Critical).

Scans an unstructured folder of theme assets and produces a valid,
complete manifest.json by detecting file types, inferring component
structure, extracting palette colors, and building variant lists.
"""

import colorsys
import hashlib
import json
import os
from typing import Any, Optional

from ..core.logger import log


class ManifestGenerator:
    """Auto-generate manifest.json from a folder of theme assets."""

    def generate(
        self,
        theme_dir: str,
        name: Optional[str] = None,
        author: Optional[str] = None,
    ) -> dict[str, Any]:
        """Full auto-generate manifest from folder. Returns result dict."""
        if not os.path.isdir(theme_dir):
            return {"success": False, "message": f"Directory not found: {theme_dir}"}

        manifest_name = name or os.path.basename(os.path.normpath(theme_dir))

        # Phase 1: Discover & classify files
        file_map = self.discover_components(theme_dir)

        # Phase 2: Build component entries
        components = self.build_component_entries(file_map)

        # Phase 3: Extract palette from wallpaper
        palette = {"background": "#2b2b2b", "accent": "#3d3d3d", "text": "#ffffff",
                   "inactive": "#1a1a1a", "border": "#555555", "active": "#ffffff"}
        if "wallpapers" in components and components["wallpapers"]["variants"]:
            first_wall = components["wallpapers"]["variants"][0]["file"]
            wall_path = os.path.join(theme_dir, first_wall)
            if os.path.exists(wall_path):
                try:
                    palette = self.extract_palette(wall_path)
                except Exception as exc:
                    log.warning("Palette extraction failed: %s", exc)

        manifest = {
            "name": manifest_name,
            "version": "1.0.0",
            "description": f"Auto-generated theme: {manifest_name}",
            "author": author or "Unknown",
            "palette": palette,
            "components": components,
        }

        # Phase 4: Validate
        warnings = self.validate_generated(manifest)

        manifest_path = os.path.join(theme_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        comp_count = sum(
            1 for c in components.values()
            if "variants" in c and c["variants"]
        )

        return {
            "success": True,
            "manifest_path": manifest_path,
            "components": comp_count,
            "warnings": warnings,
        }

    def discover_components(self, theme_dir: str) -> dict[str, list[str]]:
        """Phase 1: Recursively scan directory and classify files by type."""
        file_map: dict[str, list[str]] = {}

        for root, dirs, files in os.walk(theme_dir):
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                rel_path = os.path.relpath(os.path.join(root, filename), theme_dir)

                if ext == ".msstyles":
                    file_map.setdefault("msstyles", []).append(rel_path)
                    # Also look for paired .theme file
                    theme_candidate = rel_path.replace(".msstyles", ".theme")
                    if os.path.exists(os.path.join(theme_dir, theme_candidate)):
                        file_map.setdefault("themes", []).append(theme_candidate)
                elif ext == ".theme":
                    file_map.setdefault("themes", []).append(rel_path)
                elif ext in (".cur", ".ani"):
                    file_map.setdefault("cursors", []).append(rel_path)
                elif ext in (".ttf", ".otf", ".woff", ".woff2"):
                    file_map.setdefault("fonts", []).append(rel_path)
                elif ext in (".jpg", ".jpeg", ".png", ".bmp"):
                    # Heuristic: large images are wallpapers
                    try:
                        size = os.path.getsize(os.path.join(root, filename))
                        if size > 100 * 1024:  # > 100KB
                            file_map.setdefault("wallpapers", []).append(rel_path)
                        else:
                            file_map.setdefault("previews", []).append(rel_path)
                    except OSError:
                        file_map.setdefault("wallpapers", []).append(rel_path)
                elif ext == ".ico":
                    file_map.setdefault("icons", []).append(rel_path)
                elif ext in (".yaml", ".yml", ".ini"):
                    file_map.setdefault("windhawk_mods", []).append(rel_path)
                elif filename in ("userChrome.css", "userContent.css"):
                    file_map.setdefault("firefox", []).append(rel_path)
                elif ext == ".json":
                    file_map.setdefault("json", []).append(rel_path)

        return file_map

    def build_component_entries(self, file_map: dict[str, list[str]]) -> dict[str, Any]:
        """Phase 2: Group files into component entries with variant lists."""
        components: dict[str, Any] = {}

        # Msstyles -> variants
        if file_map.get("msstyles"):
            variants = []
            for path in file_map["msstyles"]:
                name = os.path.splitext(os.path.basename(path))[0]
                variant = {"name": name, "file": path}
                # Check for preview
                preview_base = os.path.splitext(path)[0] + ".png"
                if file_map.get("previews") and any(preview_base in p for p in file_map["previews"]):
                    variant["preview"] = preview_base
                variants.append(variant)
            if variants:
                components["msstyles"] = {"variants": variants}

        # Themes -> variants
        if file_map.get("themes"):
            variants = [
                {"name": os.path.splitext(os.path.basename(p))[0], "file": p}
                for p in file_map["themes"]
            ]
            if variants:
                components["themes"] = {"variants": variants}

        # Wallpapers -> variants
        if file_map.get("wallpapers"):
            variants = [
                {"name": f"Wallpaper {i+1}", "file": p}
                for i, p in enumerate(file_map["wallpapers"])
            ]
            if variants:
                components["wallpapers"] = {"variants": variants}

        # Cursors -> folder path
        if file_map.get("cursors"):
            # Find common parent
            parent = os.path.commonpath(file_map["cursors"])
            components["cursors"] = {"path": parent} if parent else {"path": "cursors"}

        # Fonts -> variants
        if file_map.get("fonts"):
            variants = []
            for path in file_map["fonts"]:
                name = os.path.splitext(os.path.basename(path))[0]
                variants.append({"name": name, "file": path})
            if variants:
                components["fonts"] = {"variants": variants}

        # Firefox
        if file_map.get("firefox"):
            parent = os.path.commonpath(file_map["firefox"])
            components["firefox"] = {"path": parent} if parent else {"path": "chrome"}

        return components

    def extract_palette(self, image_path: str) -> dict[str, str]:
        """Phase 3: Extract dominant colors from wallpaper using k-means on pixel data."""
        try:
            from PIL import Image
            import numpy as np

            img = Image.open(image_path).convert("RGB")
            img = img.resize((64, 64), Image.LANCZOS)
            pixels = np.array(img).reshape(-1, 3)

            # Simple k-means with k=6
            k = 6
            centroids = pixels[np.random.choice(pixels.shape[0], k, replace=False)].astype(float)

            for _ in range(20):
                distances = np.linalg.norm(pixels[:, None] - centroids[None], axis=2)
                labels = np.argmin(distances, axis=1)
                new_centroids = np.array([
                    pixels[labels == i].mean(axis=0) if np.any(labels == i) else centroids[i]
                    for i in range(k)
                ])
                if np.allclose(centroids, new_centroids):
                    break
                centroids = new_centroids

            # Sort by luminance
            luminance = 0.299 * centroids[:, 0] + 0.587 * centroids[:, 1] + 0.114 * centroids[:, 2]
            sorted_idx = np.argsort(luminance)

            hex_colors = [
                f"#{int(c[0]):02x}{int(c[1]):02x}{int(c[2]):02x}"
                for c in centroids[sorted_idx]
            ]

            return {
                "background": hex_colors[0] if len(hex_colors) > 0 else "#2b2b2b",
                "accent": hex_colors[1] if len(hex_colors) > 1 else "#3d3d3d",
                "text": hex_colors[-1] if len(hex_colors) > 2 else "#ffffff",
                "inactive": hex_colors[2] if len(hex_colors) > 3 else "#1a1a1a",
                "border": hex_colors[3] if len(hex_colors) > 4 else "#555555",
                "active": hex_colors[-1] if len(hex_colors) > 0 else "#ffffff",
            }
        except ImportError:
            log.warning("PIL/numpy not available for palette extraction; using defaults")
            return {"background": "#2b2b2b", "accent": "#3d3d3d", "text": "#ffffff",
                    "inactive": "#1a1a1a", "border": "#555555", "active": "#ffffff"}

    def validate_generated(self, manifest: dict) -> list[str]:
        """Phase 4: Verify completeness, emit warnings."""
        warnings = []
        components = manifest.get("components", {})

        required = {"msstyles", "wallpapers"}
        for req in required:
            if req not in components:
                warnings.append(f"Missing recommended component: {req}")

        for comp_type, comp_data in components.items():
            if "variants" in comp_data and not comp_data["variants"]:
                warnings.append(f"Component '{comp_type}' has empty variants")

        if not warnings:
            warnings.append("All checks passed")

        return warnings