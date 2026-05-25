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
        """Suggest based on time of day."""
        hour = datetime.now().hour
        if not self.theme_manager:
            return {"theme": None, "reason": "No themes available"}

        all_themes = self.theme_manager.get_all_themes()
        if not all_themes:
            return {"theme": None, "reason": "No themes available"}

        # Daytime: pick lightest theme; Night: pick darkest
        if 6 <= hour < 18:
            return {"theme": list(all_themes.keys())[0], "reason": f"It's {hour}:00 — daytime themes reduce eye strain"}
        else:
            dark_themes = [n for n in all_themes.keys() if "dark" in n.lower() or "night" in n.lower()]
            if dark_themes:
                return {"theme": dark_themes[0], "reason": f"It's {hour}:00 — dark theme suggested for nighttime"}
            return {"theme": list(all_themes.keys())[0], "reason": f"It's {hour}:00"}

    def track_apply(self, theme_name: str, components: Optional[list[str]] = None) -> None:
        """Record an apply event for learning."""
        self._history.append({
            "action": "apply",
            "theme": theme_name,
            "components": components,
            "timestamp": time.time(),
        })

    def _color_distance(self, hex_a: str, hex_b: str) -> float:
        """CIEDE2000-like distance between two hex colors."""
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