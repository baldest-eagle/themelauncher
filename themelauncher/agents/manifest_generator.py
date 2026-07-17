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
from .preview_generator import PreviewGenerator


class ManifestGenerator:
    """Auto-generate manifest.json from a folder of theme assets."""

    def __init__(self):
        self.preview_gen = PreviewGenerator()

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

        # Phase 0: Organize folder into standard structure
        self.organize_folder(theme_dir)

        # Phase 1: Discover & classify files
        file_map = self.discover_components(theme_dir)

        # Phase 2: Build component entries
        components = self.build_component_entries(file_map, theme_dir)

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

        # Phase 3.5: Generate previews for components
        self.generate_component_previews(components, theme_dir)

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

                # Skip files in the guides folders - they should be detected by guide component
                if "guide" in root.lower() or root.endswith("guides"):
                    continue

                if ext == ".msstyles":
                    file_map.setdefault("msstyles", []).append(rel_path)
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
                    try:
                        size = os.path.getsize(os.path.join(root, filename))
                        if size > 100 * 1024:
                            file_map.setdefault("wallpapers", []).append(rel_path)
                    except OSError:
                        pass
                elif ext == ".ico":
                    file_map.setdefault("icons", []).append(rel_path)
                elif ext in (".yaml", ".yml", ".ini"):
                    file_map.setdefault("windhawk_mods", []).append(rel_path)
                elif filename in ("userChrome.css", "userContent.css"):
                    file_map.setdefault("firefox", []).append(rel_path)
                elif ext == ".json":
                    file_map.setdefault("json", []).append(rel_path)

        return file_map

    def organize_folder(self, theme_dir: str) -> None:
        """Organize theme folder into standard structure. Create missing folders."""
        for folder in ["wallpapers", "cursors", "fonts", "icons", "themes", "windhawk", "firefox"]:
            os.makedirs(os.path.join(theme_dir, folder), exist_ok=True)

    def build_component_entries(self, file_map: dict[str, list[str]], theme_dir: str) -> dict[str, Any]:
        """Phase 2: Group files into component entries with variant lists."""
        components: dict[str, Any] = {}

        if file_map.get("msstyles"):
            variants = []
            for path in file_map["msstyles"]:
                # If it's in a StartAllBack folder, skip it here (handled later)
                if "startallback" in path.lower() or "sab" in path.lower():
                    continue
                name = os.path.splitext(os.path.basename(path))[0]
                variant = {"name": name, "file": path}
                variants.append(variant)
            if variants:
                components["msstyles"] = {"variants": variants}

        if file_map.get("themes"):
            variants = [
                {"name": os.path.splitext(os.path.basename(p))[0], "file": p}
                for p in file_map["themes"]
            ]
            if variants:
                components["themes"] = {"variants": variants}

        if file_map.get("wallpapers"):
            variants = [
                {"name": f"Wallpaper {i+1}", "file": p}
                for i, p in enumerate(file_map["wallpapers"])
            ]
            if variants:
                components["wallpapers"] = {"variants": variants}

        if file_map.get("cursors"):
            # Find the most likely path containing cursors
            parent = os.path.commonpath(file_map["cursors"])
            components["cursors"] = {"path": parent} if parent else {"path": "cursors"}

        if file_map.get("fonts"):
            variants = []
            for path in file_map["fonts"]:
                name = os.path.splitext(os.path.basename(path))[0]
                variants.append({"name": name, "file": path})
            if variants:
                components["fonts"] = {"variants": variants}

        if file_map.get("firefox"):
            parent = os.path.commonpath(file_map["firefox"])
            components["firefox"] = {"path": parent} if parent else {"path": "chrome"}

        # --- Enhanced Detection ---

        # 1. Icons
        if file_map.get("icons"):
            variants = []
            for path in file_map["icons"]:
                name = os.path.splitext(os.path.basename(path))[0]
                variants.append({"name": name, "file": path})
            if variants:
                components["icons"] = {"variants": variants}

        # 2. Windhawk Mods
        if file_map.get("windhawk_mods"):
            variants = []
            for path in file_map["windhawk_mods"]:
                name = os.path.splitext(os.path.basename(path))[0]
                variants.append({"name": name, "file": path})
            if variants:
                components["windhawk"] = {"variants": variants}

        # 3. Resource Redirect (theme.ini)
        theme_ini = None
        for root, dirs, files in os.walk(theme_dir):
            if "theme.ini" in files:
                theme_ini = os.path.relpath(os.path.join(root, "theme.ini"), theme_dir)
                break
        if theme_ini:
            components["resource_redirect"] = {"path": os.path.dirname(theme_ini)}

        # 4. StartOrb
        orb_files = []
        for root, dirs, files in os.walk(theme_dir):
            if "orb" in root.lower() or "start" in root.lower():
                for f in files:
                    if f.lower().endswith((".png", ".bmp", ".svg")):
                        orb_files.append(os.path.relpath(os.path.join(root, f), theme_dir))
        if orb_files:
            variants = [{"name": os.path.splitext(os.path.basename(p))[0], "file": p} for p in orb_files]
            components["startorb"] = {"variants": variants}

        # 5. StartAllBack
        sab_styles = []
        for path in file_map.get("msstyles", []):
            if "startallback" in path.lower() or "sab" in path.lower():
                sab_styles.append(path)
        if sab_styles:
            variants = [{"name": os.path.splitext(os.path.basename(p))[0], "file": p} for p in sab_styles]
            components["startallback"] = {"variants": variants}

        # 6. MicaForEveryone
        mica_json = None
        for root, dirs, files in os.walk(theme_dir):
            if "mica" in root.lower():
                for f in files:
                    if f.lower().endswith(".json"):
                        mica_json = os.path.relpath(os.path.join(root, f), theme_dir)
                        break
        if mica_json:
            components["mica"] = {"settings_json": mica_json}

        # 7. OldNewExplorer
        one_reg = None
        for root, dirs, files in os.walk(theme_dir):
            for f in files:
                if "oldnewexplorer" in f.lower() and f.lower().endswith(".reg"):
                    one_reg = os.path.relpath(os.path.join(root, f), theme_dir)
                    break
        if one_reg:
            components["oldnewexplorer"] = {"reg_file": one_reg}

        return components

    def generate_component_previews(self, components: dict, theme_dir: str):
        """Automate preview generation for variants using the Preview Bot engine."""
        preview_dir = os.path.join(theme_dir, "previews")
        os.makedirs(preview_dir, exist_ok=True)

        # MSSTYLES
        if "msstyles" in components:
            for variant in components["msstyles"].get("variants", []):
                file_rel = variant.get("file")
                file_abs = os.path.join(theme_dir, file_rel)
                out_filename = f"preview_msstyles_{variant['name']}.png"
                out_path = os.path.join(preview_dir, out_filename)
                
                if self.preview_gen.generate_from_msstyles(file_abs, out_path):
                    variant["preview"] = os.path.relpath(out_path, theme_dir)

        # THEMES
        if "themes" in components:
            for variant in components["themes"].get("variants", []):
                file_rel = variant.get("file")
                file_abs = os.path.join(theme_dir, file_rel)
                out_filename = f"preview_themes_{variant['name']}.png"
                out_path = os.path.join(preview_dir, out_filename)
                
                # Use theme generator if it's a .theme file
                if file_rel.endswith(".theme"):
                    if self.preview_gen.generate_from_theme(file_abs, out_path):
                        variant["preview"] = os.path.relpath(out_path, theme_dir)

    def extract_palette(self, image_path: str) -> dict[str, str]:
        try:
            from PIL import Image
            import numpy as np

            img = Image.open(image_path).convert("RGB")
            img = img.resize((64, 64), Image.LANCZOS)
            pixels = np.array(img).reshape(-1, 3)

            # Simple k-means with k=6. Seed the RNG (and the initial centroid
            # choice) so palette extraction is reproducible run-to-run —
            # previously np.random.choice produced a different palette every
            # call from the same wallpaper.
            k = 6
            rng = np.random.default_rng(42)
            centroids = pixels[rng.choice(pixels.shape[0], k, replace=False)].astype(float)

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