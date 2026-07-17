"""Theme Diff Engine Agent (Tier 3 - Enhancement). Version control for themes."""

import json
import os
from typing import Any, Optional

from ..core.logger import log


class DiffEngine:
    """Compare themes structurally: manifests, palettes, and component lists."""

    def diff_themes(self, theme_a: str, theme_b: str,
                    manifest_a: Optional[dict] = None,
                    manifest_b: Optional[dict] = None) -> dict[str, Any]:
        """Compare two themes structurally."""
        if not manifest_a or not manifest_b:
            return {"error": "Both manifests must be provided"}

        changes: dict[str, Any] = {
            "added_components": [],
            "removed_components": [],
            "changed_variants": [],
            "palette_changes": {},
        }

        comps_a = manifest_a.get("components", {})
        comps_b = manifest_b.get("components", {})

        # Find added/removed components
        added = set(comps_b.keys()) - set(comps_a.keys())
        removed = set(comps_a.keys()) - set(comps_b.keys())
        changes["added_components"] = list(added)
        changes["removed_components"] = list(removed)

        # Find changed variants
        common = set(comps_a.keys()) & set(comps_b.keys())
        for comp in common:
            # Guard against malformed variant entries (missing "name", or
            # variant not a dict). Previously ``v["name"]`` raised KeyError.
            def _variant_names(comp_data: Any) -> set[str]:
                names: set[str] = set()
                variants = comp_data.get("variants", []) if isinstance(comp_data, dict) else []
                if not isinstance(variants, list):
                    return names
                for v in variants:
                    if isinstance(v, dict):
                        n = v.get("name")
                        if isinstance(n, str):
                            names.add(n)
                return names
            variants_a = _variant_names(comps_a[comp])
            variants_b = _variant_names(comps_b[comp])
            if variants_a != variants_b:
                changes["changed_variants"].append({
                    "component": comp,
                    "added": list(variants_b - variants_a),
                    "removed": list(variants_a - variants_b),
                })

        # Diff palettes
        pal_a = manifest_a.get("palette", {})
        pal_b = manifest_b.get("palette", {})
        for key in set(list(pal_a.keys()) + list(pal_b.keys())):
            if pal_a.get(key) != pal_b.get(key):
                changes["palette_changes"][key] = {
                    "old": pal_a.get(key),
                    "new": pal_b.get(key),
                }

        return changes

    def diff_manifests(self, old_manifest: dict, new_manifest: dict) -> dict[str, Any]:
        """Compare two manifest versions."""
        return self.diff_themes("old", "new", old_manifest, new_manifest)

    def diff_palettes(self, palette_a: dict, palette_b: dict) -> list[dict[str, str]]:
        """Visual comparison of color differences."""
        diffs = []
        for key in set(list(palette_a.keys()) + list(palette_b.keys())):
            if palette_a.get(key) != palette_b.get(key):
                diffs.append({
                    "key": key,
                    "old": palette_a.get(key, ""),
                    "new": palette_b.get(key, ""),
                })
        return diffs