"""Smart Theme Recommender Agent (Tier 2 - High Value). Palette-based suggestions."""

import colorsys
import json
import math
import os
import time
from datetime import datetime
from typing import Any, Optional

from ..core.logger import log


class Recommender:
    """Recommend themes based on palette similarity, time of day, and user behavior."""

    def __init__(self, theme_manager=None):
        self.theme_manager = theme_manager
        self._history: list[dict] = []

    def recommend(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get personalized theme recommendations."""
        if not self.theme_manager:
            return []

        recommendations = []
        current_theme = self.theme_manager.active_theme

        for theme_name, theme_data in self.theme_manager.get_all_themes().items():
            if theme_name == current_theme:
                continue
            palette = theme_data["manifest"].get("palette", {})
            recommendations.append({
                "name": theme_name,
                "palette": palette,
                "reason": "Available in your library",
            })

        # Sort by some heuristic (e.g., accent color similarity to current)
        if current_theme:
            current = self.theme_manager.get_theme(current_theme)
            if current:
                current_accent = current["manifest"].get("palette", {}).get("accent", "#000000")
                for rec in recommendations:
                    dist = self._color_distance(current_accent, rec["palette"].get("accent", "#000000"))
                    rec["_distance"] = dist
                    if dist < 15:
                        rec["reason"] = "Similar accent color"
                    elif dist < 30:
                        rec["reason"] = "Complementary palette"
                    else:
                        rec["reason"] = "Bold contrast"

                recommendations.sort(key=lambda r: r.get("_distance", 999))

        return recommendations[:limit]

    def similar_to(self, theme_name: str, limit: int = 5) -> list[dict[str, Any]]:
        """Find palette-similar themes."""
        if not self.theme_manager:
            return []
        target = self.theme_manager.get_theme(theme_name)
        if not target:
            return []

        target_palette = target["manifest"].get("palette", {})
        target_accent = target_palette.get("accent", "#000000")

        similar = []
        for name, data in self.theme_manager.get_all_themes().items():
            if name == theme_name:
                continue
            dist = self._color_distance(
                target_accent,
                data["manifest"].get("palette", {}).get("accent", "#000000"),
            )
            similar.append({"name": name, "distance": dist, "reason": self._distance_label(dist)})

        similar.sort(key=lambda r: r["distance"])
        return similar[:limit]

    def circadian_suggest(self) -> dict[str, Any]:
        """Suggest a theme by actual mean palette luminance (Rec. 709).

        Daytime (06:00–17:59) → lightest palette (lowest eye strain in bright
        ambient light). Nighttime (18:00–05:59) → darkest palette. Previously
        this returned the first key in the dict (arbitrary hash order) for
        daytime and the first substring match for nighttime — neither was a
        real "lightest" or "darkest" pick.
        """
        hour = datetime.now().hour
        if not self.theme_manager:
            return {"theme": None, "reason": "No themes available"}

        all_themes = self.theme_manager.get_all_themes()
        if not all_themes:
            return {"theme": None, "reason": "No themes available"}

        # Compute mean luminance per theme (lower = darker).
        scored: list[tuple[float, str]] = []
        for name, data in all_themes.items():
            palette = data.get("manifest", {}).get("palette", {}) if isinstance(data, dict) else {}
            lum = self._mean_palette_luminance(palette)
            scored.append((lum, name))

        if not scored:
            return {"theme": None, "reason": "No themes available"}

        is_daytime = 6 <= hour < 18
        if is_daytime:
            # Lightest = highest luminance.
            scored.sort(key=lambda t: t[0], reverse=True)
            pick = scored[0][1]
            return {"theme": pick,
                    "reason": f"It's {hour}:00 — lightest theme '{pick}' suggested for daytime"}
        # Nighttime → darkest.
        scored.sort(key=lambda t: t[0])
        pick = scored[0][1]
        return {"theme": pick,
                "reason": f"It's {hour}:00 — darkest theme '{pick}' suggested for nighttime"}

    @staticmethod
    def _mean_palette_luminance(palette: dict[str, str]) -> float:
        """Mean Rec. 709 luminance across all hex colors in ``palette``.

        Channels are sRGB-linearized per WCAG 2.1 before applying the
        coefficients so mid-tones aren't underestimated.
        """
        if not palette:
            return 0.0
        total = 0.0
        count = 0
        for v in palette.values():
            if not isinstance(v, str) or not v.startswith("#") or len(v) < 7:
                continue
            try:
                h = v.lstrip("#")
                r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
            except (ValueError, IndexError):
                continue
            rl = r / 12.92 if r <= 0.03928 else ((r + 0.055) / 1.055) ** 2.4
            gl = g / 12.92 if g <= 0.03928 else ((g + 0.055) / 1.055) ** 2.4
            bl = b / 12.92 if b <= 0.03928 else ((b + 0.055) / 1.055) ** 2.4
            total += 0.2126 * rl + 0.7152 * gl + 0.0722 * bl
            count += 1
        return total / count if count else 0.0

    def track_apply(self, theme_name: str, components: Optional[list[str]] = None) -> None:
        """Record an apply event for learning.

        History is bounded to the most recent 200 entries so a long-running
        process doesn't accumulate unbounded memory.
        """
        self._history.append({
            "action": "apply",
            "theme": theme_name,
            "components": components,
            "timestamp": time.time(),
        })
        if len(self._history) > 200:
            # Trim to the most recent 200 entries.
            del self._history[: len(self._history) - 200]

    def _color_distance(self, hex_a: str, hex_b: str) -> float:
        """Euclidean sRGB distance between two hex colors.

        Note: this is a simple ``sqrt(Δr² + Δg² + Δb²)`` over raw sRGB values,
        NOT a perceptually-uniform CIEDE2000 distance (despite the previous
        docstring's claim). It's good enough for ranking palette similarity
        but should not be presented as perceptually accurate.
        """
        def _to_rgb(h):
            h = h.lstrip("#")
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

        r1, g1, b1 = _to_rgb(hex_a)
        r2, g2, b2 = _to_rgb(hex_b)
        return math.sqrt((r1 - r2)**2 + (g1 - g2)**2 + (b1 - b2)**2)

    @staticmethod
    def _distance_label(d: float) -> str:
        if d < 50:
            return "Very similar palette"
        elif d < 150:
            return "Somewhat similar"
        elif d < 300:
            return "Complementary palette"
        return "Bold contrast"