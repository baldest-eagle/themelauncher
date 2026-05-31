"""
Auto-Variant Generator Agent (Tier 1 - Critical).

Leverages HSV recoloring to automatically derive alternate variants
(dark, light, high-contrast, warm, cool, colorblind-safe) from any theme palette.
"""

import colorsys
import copy
import json
import os
from typing import Any, Optional

from ..core.logger import log


class VariantGenerator:
    """Derive alternate color variants from a theme palette."""

    def _is_variant_provided(self, theme_dir: str, variant_type: str) -> bool:
        if not os.path.isdir(theme_dir):
            return False

        v_lower = variant_type.lower()

        # 1. Check manifest.json first for existing variants in components
        manifest_path = os.path.join(theme_dir, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                components = manifest.get("components", {})
                for comp_data in components.values():
                    if isinstance(comp_data, dict):
                        variants = comp_data.get("variants", [])
                        for var in variants:
                            if isinstance(var, dict):
                                name = var.get("name", "").lower()
                                file_path = var.get("file", "").lower()
                                if v_lower in name or v_lower in file_path:
                                    log.info(
                                        "Variant '%s' found in manifest for theme at %s (Name: '%s', File: '%s')",
                                        variant_type, theme_dir, var.get("name"), var.get("file")
                                    )
                                    return True
            except Exception as e:
                log.warning("Could not parse manifest at %s to check variants: %s", manifest_path, e)

        # 2. Check files on disk recursively
        for root, _, files in os.walk(theme_dir):
            for file in files:
                if v_lower in file.lower():
                    log.info(
                        "Variant '%s' file match found on disk: %s",
                        variant_type, os.path.join(root, file)
                    )
                    return True

        return False

    def generate_variants(
        self,
        theme_name: str,
        palette: dict[str, str],
        types: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Generate specified variant types for a theme palette.

        Only creates 'light', 'dark', and 'slate' variants, and skips any that
        are already provided by the theme files or manifest.
        """
        if types is None:
            types = ["dark", "light", "slate"]

        # Resolve theme directory to check provided files
        import json
        config_path = "config.json"
        themes_dir = "themes"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    themes_dir = config.get("themes_directory", "themes")
            except Exception:
                pass
        theme_dir = os.path.join(themes_dir, theme_name)

        variants = {}
        skipped = []
        for vt in types:
            # Ensure we only generate light/dark/slate
            if vt not in ["dark", "light", "slate"]:
                continue

            if self._is_variant_provided(theme_dir, vt):
                log.info("Skipping variant '%s' for '%s': already provided by theme files", vt, theme_name)
                skipped.append(vt)
                continue

            if vt == "dark":
                variants["dark"] = self.derive_dark_palette(palette)
            elif vt == "light":
                variants["light"] = self.derive_light_palette(palette)
            elif vt == "slate":
                variants["slate"] = self.derive_slate_palette(palette)

        return {
            "generated": len(variants),
            "variants": variants,
            "skipped_provided": skipped
        }

    def _hex_to_hsv(self, hex_color: str) -> tuple[float, float, float]:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
        return colorsys.rgb_to_hsv(r, g, b)

    def _hsv_to_hex(self, h: float, s: float, v: float) -> str:
        r, g, b = colorsys.hsv_to_rgb(h % 1.0, max(0, min(1, s)), max(0, min(1, v)))
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    def _transform_palette(self, palette: dict[str, str], fn) -> dict[str, str]:
        result = {}
        for key, val in palette.items():
            h, s, v = self._hex_to_hsv(val)
            result[key] = fn(h, s, v) if callable(fn) else self._hsv_to_hex(h, s, v)
        return result

    def derive_dark_palette(self, palette: dict[str, str]) -> dict[str, str]:
        """Invert lightness, swap bg/fg."""
        def _dark(h, s, v):
            return self._hsv_to_hex(h, s, 1.0 - v * 0.7)
        result = self._transform_palette(palette, _dark)
        # Swap bg and fg-like roles
        if "background" in result and "text" in result:
            bg, txt = result["background"], result["text"]
            result["background"] = txt
            result["text"] = bg
        return result

    def derive_light_palette(self, palette: dict[str, str]) -> dict[str, str]:
        """Invert toward light."""
        def _light(h, s, v):
            return self._hsv_to_hex(h, s * 0.5, min(1, v * 1.5))
        return self._transform_palette(palette, _light)

    def derive_slate_palette(self, palette: dict[str, str]) -> dict[str, str]:
        """Derive a muted, bluish-gray slate variant."""
        def _slate(h, s, v):
            new_h = 0.583  # 210 degrees (slate blue)
            new_s = max(0.08, min(0.25, s * 0.4))
            new_v = max(0.15, min(0.9, v))
            return self._hsv_to_hex(new_h, new_s, new_v)
        return self._transform_palette(palette, _slate)

    def derive_high_contrast(self, palette: dict[str, str]) -> dict[str, str]:
        """Max saturation, extend lightness gap."""
        def _hc(h, s, v):
            return self._hsv_to_hex(h, 1.0, max(0, min(1, v)))
        result = self._transform_palette(palette, _hc)
        # Ensure bg is very dark, text is very light
        bg_v = self._hex_to_hsv(result.get("background", "#000000"))[2]
        txt_v = self._hex_to_hsv(result.get("text", "#ffffff"))[2]
        if bg_v > 0.3:
            result["background"] = self._hsv_to_hex(
                self._hex_to_hsv(result["background"])[0], 1.0, 0.1
            )
        if txt_v < 0.7:
            result["text"] = self._hsv_to_hex(
                self._hex_to_hsv(result["text"])[0], 0.0, 0.95
            )
        return result

    def derive_hue_shift(self, palette: dict[str, str], degrees: float) -> dict[str, str]:
        """Rotate all hues by specified degrees."""
        shift = degrees / 360.0
        def _shift(h, s, v):
            return self._hsv_to_hex(h + shift, s, v)
        return self._transform_palette(palette, _shift)

    def derive_colorblind_safe(self, palette: dict[str, str]) -> dict[str, str]:
        """Simple adaptation: avoid red-green confusion by shifting reds toward blue."""
        def _cb(h, s, v):
            # Shift reds (h ~ 0.0-0.1) toward blue
            if h < 0.1 or h > 0.9:
                h = (h + 0.55) % 1.0
            return self._hsv_to_hex(h, s, v)
        return self._transform_palette(palette, _cb)

    def save_variants(
        self,
        theme_name: str,
        variants: dict[str, dict[str, str]],
        output_dir: str,
    ) -> None:
        """Save variant palettes to JSON files."""
        variants_dir = os.path.join(output_dir, "variants")
        os.makedirs(variants_dir, exist_ok=True)

        with open(os.path.join(variants_dir, "palettes.json"), "w") as f:
            json.dump(variants, f, indent=2)

        log.info("Saved %d variant palettes for '%s'", len(variants), theme_name)