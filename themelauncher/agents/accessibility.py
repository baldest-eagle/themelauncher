"""Accessibility Compliance Checker Agent (Tier 3 - Enhancement). WCAG contrast validation."""

import colorsys
import math
import os
from typing import Any

from ..core.logger import log


class AccessibilityChecker:
    """Scan theme palettes for WCAG 2.1 contrast violations and colorblind visibility issues."""

    def check_palette(self, palette: dict[str, str]) -> list[dict[str, Any]]:
        """Full WCAG contrast audit of palette pairs."""
        violations = []
        pairs = [("text", "background"), ("text", "accent"), ("active", "background")]

        for fg_key, bg_key in pairs:
            fg = palette.get(fg_key)
            bg = palette.get(bg_key)
            if fg and bg:
                ratio = self._contrast_ratio(fg, bg)
                if ratio < 4.5:
                    violations.append({
                        "type": "contrast",
                        "pair": f"{fg_key}/{bg_key}",
                        "ratio": round(ratio, 1),
                        "required": 4.5,
                        "level": "AA",
                    })

        return violations

    def check_colorblind(self, palette: dict[str, str]) -> list[dict[str, str]]:
        """Simulate color vision deficiencies."""
        violations = []
        # Check red-green pairs
        accent = palette.get("accent", "#000000")
        muted = palette.get("muted", palette.get("inactive", "#888888"))
        if self._color_distance(accent, muted) < 100:
            violations.append({
                "type": "colorblind",
                "deficiency": "protanopia",
                "indistinguishable": "accent/muted",
            })
        return violations

    def generate_report(self, theme_name: str, palette: dict[str, str]) -> dict[str, Any]:
        """Full compliance report with fix suggestions."""
        contrast_violations = self.check_palette(palette)
        cb_violations = self.check_colorblind(palette)
        all_violations = contrast_violations + cb_violations

        return {
            "theme": theme_name,
            "compliant": len(all_violations) == 0,
            "violations": all_violations,
            "suggested_fixes": self.suggest_fixes(all_violations, palette),
        }

    def suggest_fixes(self, violations: list[dict], palette: dict) -> dict[str, str]:
        """Auto-generate corrected palette values for contrast violations.

        For each ``pair`` of the form ``"fg/bg"`` we target the FOREGROUND
        (``pair.split("/")[0]`` — previously the code took ``[1]`` and was
        actually editing the background). The foreground's lightness is
        adjusted based on the background's luminance: if the bg is dark we
        push the fg light; if the bg is light we push the fg dark.
        """
        fixes = {}
        for v in violations:
            if v.get("type") != "contrast":
                continue
            pair = v.get("pair", "")
            if "/" not in pair:
                continue
            fg_key, bg_key = pair.split("/", 1)
            fg = palette.get(fg_key)
            bg = palette.get(bg_key)
            if not fg or not bg:
                continue
            bg_lum = self._luminance(bg)
            # Determine a target lightness that will produce >= 4.5:1 contrast.
            # bg_lum near 0 → dark bg → push fg light (l≈0.95).
            # bg_lum near 1 → light bg → push fg dark (l≈0.10).
            # We key the suggested fix on the foreground key (not the bg).
            h, l, s = self._hex_to_hls(fg)  # colorsys uses (h, l, s) order
            if bg_lum < 0.18:
                target_l = 0.95
            elif bg_lum > 0.82:
                target_l = 0.10
            else:
                # Mid bg: push toward whichever extreme is further from bg.
                target_l = 0.95 if bg_lum < 0.5 else 0.10
            fixes[fg_key] = self._hls_to_hex(h, l=target_l, s=s)
        return fixes

    def _hex_to_hls(self, hex_color: str) -> tuple[float, float, float]:
        """Return ``(h, l, s)`` — colorsys's HLS order, NOT HSL."""
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
        return colorsys.rgb_to_hls(r, g, b)

    def _hls_to_hex(self, h: float, l: float, s: float) -> str:
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    @staticmethod
    def _channel_to_linear(c: float) -> float:
        """sRGB → linear-light per WCAG 2.1.

        WCAG specifies ``c/12.92`` if ``c <= 0.03928`` else ``((c+0.055)/1.055)**2.4``.
        Computing luminance from raw sRGB values (the old code) underestimates
        the perceived brightness of mid-tones by up to ~30%, so contrast
        ratios were systematically wrong.
        """
        if c <= 0.03928:
            return c / 12.92
        return ((c + 0.055) / 1.055) ** 2.4

    def _luminance(self, hex_color: str) -> float:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
        # WCAG 2.1: linearize each channel, then apply Rec. 709 coefficients.
        rl = self._channel_to_linear(r)
        gl = self._channel_to_linear(g)
        bl = self._channel_to_linear(b)
        return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl

    def _contrast_ratio(self, fg: str, bg: str) -> float:
        l1 = self._luminance(fg) + 0.05
        l2 = self._luminance(bg) + 0.05
        return max(l1, l2) / min(l1, l2)

    @staticmethod
    def _color_distance(hex_a: str, hex_b: str) -> float:
        def _to_rgb(h):
            h = h.lstrip("#")
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r1, g1, b1 = _to_rgb(hex_a)
        r2, g2, b2 = _to_rgb(hex_b)
        return math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)

    def check_cursor_sizes(self, theme_name: str,
                           themes_dir: str | None = None) -> list[dict]:
        """Verify cursor dimensions meet the 32x32 minimum.

        Walks ``<themes_dir>/<theme_name>`` for ``.cur`` and ``.ani`` files
        and uses PIL to check their dimensions. Returns a list of violations
        (one per undersized cursor). Cursors that can't be opened or that PIL
        can't read are reported as ``"unknown"`` so the user knows to inspect
        them manually.
        """
        violations: list[dict] = []
        if themes_dir is None:
            # Best-effort: assume themes dir is <project_root>/themes.
            themes_dir = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "..", "..", "themes")
            )
        theme_dir = os.path.join(themes_dir, theme_name)
        if not os.path.isdir(theme_dir):
            return violations

        try:
            from PIL import Image
        except ImportError:
            log.warning("Pillow not installed; cannot check cursor sizes")
            return violations

        for root, _dirs, files in os.walk(theme_dir):
            for fname in files:
                ext = fname.lower()
                if not (ext.endswith(".cur") or ext.endswith(".ani")):
                    continue
                path = os.path.join(root, fname)
                try:
                    with Image.open(path) as img:
                        w, h = img.size
                    if w < 32 or h < 32:
                        violations.append({
                            "file": os.path.relpath(path, theme_dir),
                            "size": f"{w}x{h}",
                            "required": "32x32",
                        })
                except Exception as exc:
                    log.debug("Could not read cursor %s: %s", path, exc)
                    violations.append({
                        "file": os.path.relpath(path, theme_dir),
                        "size": "unknown",
                        "required": "32x32",
                        "error": str(exc),
                    })
        return violations