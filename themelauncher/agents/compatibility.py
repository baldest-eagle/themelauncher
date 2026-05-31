"""
Compatibility and Conflict Detector Agent (Tier 1 - Critical).

Runs pre-flight checks before any apply or mix operation and returns
a structured report of conflicts, warnings, and informational notes.
"""

import json
import os
from typing import Any, Optional

from ..core.logger import log


class CompatibilityDetector:
    """Pre-flight conflict detection for theme applies and mixes."""

    def __init__(self, theme_manager=None):
        self.theme_manager = theme_manager

    def check_apply(self, theme_name: str, components: Optional[list[str]] = None) -> dict[str, Any]:
        """Pre-flight check before applying a complete theme."""
        if not self.theme_manager:
            return {"conflicts": 0, "warnings": 0, "info": 1,
                    "details": [{"level": "info", "type": "no_manager",
                                 "message": "No theme manager provided; compatibility check limited."}]}

        theme = self.theme_manager.get_theme(theme_name)
        if not theme:
            return {"conflicts": 1, "warnings": 0, "info": 0,
                    "details": [{"level": "conflict", "type": "missing_theme",
                                 "message": f"Theme '{theme_name}' not found."}]}

        manifest = theme["manifest"]
        all_components = manifest.get("components", {})
        check_comps = components if components else list(all_components.keys())

        results = {"conflicts": 0, "warnings": 0, "info": 0, "details": []}

        # Check completeness
        completeness = self.check_completeness(check_comps)
        results["details"].extend(completeness)
        results["warnings"] += sum(1 for d in completeness if d.get("level") == "warning")
        results["info"] += sum(1 for d in completeness if d.get("level") == "info")

        # Check resource collisions
        resource_check = self.check_resource_collision(
            {c: all_components.get(c, {}) for c in check_comps if c in all_components}
        )
        results["details"].extend(resource_check)
        results["conflicts"] += sum(1 for d in resource_check if d.get("level") == "conflict")

        return results

    def check_mix(self, slots: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Pre-flight check for a cross-theme mix."""
        results = {"conflicts": 0, "warnings": 0, "info": 0, "details": []}

        # Check if all required components are present
        comp_types = list(slots.keys())
        completeness = self.check_completeness(comp_types)
        results["details"].extend(completeness)
        results["warnings"] += sum(1 for d in completeness if d.get("level") == "warning")

        return results

    def check_windhawk_collision(self, mods_list: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Detect hook collisions between mods."""
        hooks_seen: dict[str, str] = {}
        results = []

        for mod in mods_list:
            mod_name = mod.get("name", "unknown")
            hooks = mod.get("hooks", mod.get("hook", ""))
            if isinstance(hooks, str):
                hooks = [hooks]

            for hook in hooks:
                if hook in hooks_seen:
                    results.append({
                        "level": "conflict",
                        "type": "windhawk_collision",
                        "message": f"Mods '{hooks_seen[hook]}' and '{mod_name}' both target hook '{hook}'",
                    })
                else:
                    hooks_seen[hook] = mod_name

        return results

    def check_visual_contrast(self, terminal_scheme: dict, wallpaper: str) -> list[dict[str, str]]:
        """WCAG contrast between terminal bg and wallpaper."""
        results = []
        try:
            from PIL import Image

            terminal_bg = terminal_scheme.get("background", "#000000").lstrip("#")
            if os.path.exists(wallpaper):
                img = Image.open(wallpaper).convert("RGB").resize((1, 1))
                wall_bg = "#{:02x}{:02x}{:02x}".format(*img.getpixel((0, 0)))
            else:
                wall_bg = "#000000"

            # Simple WCAG contrast check
            def _luminance(hex_color: str) -> float:
                hex_color = hex_color.lstrip("#")
                r, g, b = [int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
                return 0.2126 * r + 0.7152 * g + 0.0722 * b

            l1 = _luminance(terminal_bg)
            l2 = _luminance(wall_bg)
            lighter, darker = max(l1, l2), min(l1, l2)
            ratio = (lighter + 0.05) / (darker + 0.05)

            if ratio < 3.0:
                results.append({
                    "level": "warning",
                    "type": "low_contrast",
                    "message": f"Terminal bg vs wallpaper contrast ratio: {ratio:.1f}:1 (minimum 3:1)",
                })
        except ImportError:
            pass

        return results

    def check_resource_collision(self, components: dict[str, dict]) -> list[dict[str, str]]:
        """Detect overlapping resource_redirect targets."""
        results = []
        targets_seen: dict[str, str] = {}

        for comp_type, comp_data in components.items():
            if comp_type == "resource_redirect":
                src = comp_data.get("path", "")
                if src in targets_seen:
                    results.append({
                        "level": "conflict",
                        "type": "resource_collision",
                        "message": f"Multiple components target the same resource path: {src}",
                    })
                else:
                    targets_seen[src] = comp_type

        return results

    def check_completeness(self, components: list[str]) -> list[dict[str, str]]:
        """Warn about missing critical components."""
        results = []
        critical = {"msstyles", "wallpapers", "cursors"}

        missing = critical - set(components)
        for comp in sorted(missing):
            results.append({
                "level": "warning",
                "type": "missing_component",
                "message": f"Mix is missing '{comp}' — this component will not be applied",
            })

        if not results:
            results.append({
                "level": "info",
                "type": "complete",
                "message": "All critical components present",
            })

        return results