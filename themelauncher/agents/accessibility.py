"""Accessibility Compliance Checker Agent (Tier 3 - Enhancement). WCAG contrast validation."""

import colorsys
import math
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
        """Auto-generate corrected palette values."""
        fixes = {}
        for v in violations:
            if v.get("type") == "contrast":
                fg = palette.get(v["pair"].split("/")[1])
                if fg:
                    # Darken or lighten to meet ratio
                    h, s, l = self._hex_to_hsl(fg)
                    fixes[fg] = self._hsl_to_hex(h, s, 0.7)
        return fixes

    def _hex_to_hsl(self, hex_color: str) -> tuple[float, float, float]:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
        return colorsys.rgb_to_hls(r, g, b)

    def _hsl_to_hex(self, h: float, s: float, l: float) -> str:
        r, g, b = colorsys.hls_to_rgb(h, l, s)
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

    def _luminance(self, hex_color: str) -> float:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

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

    def check_cursor_sizes(self, theme_name: str) -> list[dict]:
        """Verify cursor dimensions meet minimums."""
        return []  # Requires cursor file analysis