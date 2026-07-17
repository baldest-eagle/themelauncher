"""
Auto-Variant Generator Agent (Tier 1 - Critical).

Leverages HSV recoloring to automatically derive alternate variants
(dark, light, high-contrast, warm, cool, colorblind-safe) from any theme palette.
"""

import colorsys
import copy
import json
import os
import re
from typing import Any, Optional

from ..core.logger import log


def _resolve_themes_dir() -> str:
    """Resolve the themes directory from the project config.

    Walks up from this module's ``__file__`` looking for a ``config.json`` at
    the project root (the same level as the ``themelauncher`` package). Reads
    ``themes_directory`` from it, falling back to ``<root>/themes``.

    Previously this read ``config.json`` from the process CWD, which broke
    whenever the app was launched from a different working directory (e.g.
    a Start Menu shortcut sets CWD to System32).
    """
    here = os.path.abspath(os.path.dirname(__file__))
    # here = .../themelauncher/themelauncher/agents/variant_generator.py
    # walk up: agents/ → themelauncher/ → themelauncher/ → project root
    for up in ("..", "..", ".."):
        here = os.path.abspath(os.path.join(here, up))
        cfg = os.path.join(here, "config.json")
        if os.path.exists(cfg):
            try:
                with open(cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                td = data.get("themes_directory", "")
                if td:
                    if os.path.isabs(td):
                        return td
                    return os.path.join(here, td)
            except Exception:
                pass
    # Fallback: <project_root>/themes
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(root, "themes")


class VariantGenerator:
    """Derive alternate color variants from a theme palette."""

    def _is_variant_provided(self, theme_dir: str, variant_type: str) -> bool:
        if not os.path.isdir(theme_dir):
            return False

        v_lower = variant_type.lower()
        # Word-boundary match so "dark" does NOT match "darkforest" (was a
        # false positive with substring ``in``).
        word_re = re.compile(r"\b" + re.escape(v_lower) + r"\b", re.IGNORECASE)

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
                                name = var.get("name", "") or ""
                                file_path = var.get("file", "") or ""
                                if word_re.search(name) or word_re.search(file_path):
                                    log.info(
                                        "Variant '%s' found in manifest for theme at %s "
                                        "(Name: '%s', File: '%s')",
                                        variant_type, theme_dir, var.get("name"), var.get("file")
                                    )
                                    return True
            except Exception as e:
                log.warning("Could not parse manifest at %s to check variants: %s", manifest_path, e)

        # 2. Check filename STEMS (not full filenames) on disk recursively.
        # E.g. ``dark.ttf`` matches "dark" but ``darkforest.ttf`` does not.
        for root, _, files in os.walk(theme_dir):
            for file in files:
                stem = os.path.splitext(file)[0]
                if word_re.search(stem):
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

        Accepts ``dark``, ``light``, ``slate``, ``high_contrast``,
        ``colorblind_safe``, and ``hue_shift``. Any variant that is already
        provided by the theme files or manifest is skipped.
        """
        if types is None:
            types = ["dark", "light", "slate"]

        # Resolve theme directory via the project config (NOT the process CWD).
        themes_dir = _resolve_themes_dir()
        theme_dir = os.path.join(themes_dir, theme_name)

        supported = {
            "dark": self.derive_dark_palette,
            "light": self.derive_light_palette,
            "slate": self.derive_slate_palette,
            "high_contrast": self.derive_high_contrast,
            "colorblind_safe": self.derive_colorblind_safe,
            # hue_shift takes an extra ``degrees`` arg; special-case below.
            "hue_shift": None,
        }

        variants = {}
        skipped = []
        for vt in types:
            key = vt.lower()
            if key not in supported:
                log.warning("Unsupported variant type '%s'; skipping", vt)
                continue

            if self._is_variant_provided(theme_dir, key):
                log.info("Skipping variant '%s' for '%s': already provided by theme files", vt, theme_name)
                skipped.append(vt)
                continue

            if key == "hue_shift":
                variants["hue_shift"] = self.derive_hue_shift(palette, degrees=30)
            else:
                fn = supported[key]
                variants[key] = fn(palette)

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
        """Derive a dark variant using explicit lightness targets.

        Previously this used ``v' = 1.0 - v * 0.7`` which is self-cancelling
        for already-dark colors (a dark color stays dark, a light color flips
        dark — but then the bg/text swap re-inverts it, so the result was
        essentially the input palette for any sensible input).

        Now we use explicit lightness targets keyed on the palette key name:
          * ``background``/``bg``/``surface`` → very dark value (0.12)
          * ``text``/``fg``/``foreground``   → very light value (0.95)
          * ``accent``/``primary``           → moderate value (0.55), full sat
          * everything else                  → lightness only modestly changed
        """
        dark_keys = ("background", "bg", "surface", "base", "panel")
        light_keys = ("text", "fg", "foreground", "label", "title")
        accent_keys = ("accent", "primary", "active", "selection")

        result: dict[str, str] = {}
        for key, hex_color in palette.items():
            h, s, v = self._hex_to_hsv(hex_color)
            k_lower = key.lower()
            if any(k in k_lower for k in dark_keys):
                new_v = 0.12
                new_s = min(s, 0.35)  # mute so we don't get neon backgrounds
            elif any(k in k_lower for k in light_keys):
                new_v = 0.95
                new_s = min(s, 0.20)
            elif any(k in k_lower for k in accent_keys):
                new_v = 0.55
                new_s = max(s, 0.65)  # keep accents punchy
            else:
                # Generic key: shift toward dark without going pure black.
                new_v = max(0.18, min(0.40, v * 0.5))
                new_s = s
            result[key] = self._hsv_to_hex(h, new_s, new_v)
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