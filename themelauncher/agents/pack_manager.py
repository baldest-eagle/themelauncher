"""Pack Manager Agent (Tier 2 - High Value). Auto-sort, validate, and import theme packs."""

import json
import os
import shutil
from typing import Any, Callable, Optional

from ..core.logger import log


class PackManager:
    """Automated theme pack management with directory watching and validation."""

    def __init__(self, themes_dir: str = ""):
        self.themes_dir = themes_dir
        self._quarantine_dir = ""

    def validate_pack(self, path: str) -> dict[str, Any]:
        """Check manifest, file refs, and palette integrity."""
        manifest_path = os.path.join(path, "manifest.json")
        if not os.path.exists(manifest_path):
            return {"success": False, "message": "No manifest.json found"}

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except json.JSONDecodeError as exc:
            return {"success": False, "message": f"Invalid JSON in manifest: {exc}"}

        errors = []
        if "name" not in manifest:
            errors.append("Missing 'name'")
        if "version" not in manifest:
            errors.append("Missing 'version'")
        if "palette" not in manifest:
            errors.append("Missing 'palette'")

        components = manifest.get("components", {})
        for comp_type, comp_data in components.items():
            if "variants" in comp_data:
                for i, v in enumerate(comp_data["variants"]):
                    file_path = os.path.join(path, v.get("file", ""))
                    if not os.path.exists(file_path):
                        errors.append(f"Variant '{v.get('name')}' file missing: {v.get('file')}")

        return {
            "success": len(errors) == 0,
            "message": "; ".join(errors) if errors else "Valid",
            "errors": errors,
        }

    def auto_import(self, watch_dir: str, callback: Optional[Callable] = None) -> None:
        """Simple import of all theme packs in a directory."""
        if not os.path.isdir(watch_dir):
            log.warning("Watch directory not found: %s", watch_dir)
            return

        for entry in os.listdir(watch_dir):
            entry_path = os.path.join(watch_dir, entry)
            if os.path.isdir(entry_path):
                result = self.validate_pack(entry_path)
                if callback:
                    callback({"path": entry, "success": result["success"], "message": result["message"]})

    def sort_themes(self, themes_dir: str, by: str = "name") -> dict[str, Any]:
        """Return a sorted list of manifest entries from ``themes_dir``.

        Reads every ``manifest.json`` under ``themes_dir`` (one per theme) and
        sorts the resulting list by ``by`` — either ``"name"`` (default) or
        ``"author"``. Themes with missing/invalid manifests are sorted to the
        end. Previously this was a placeholder that just returned a message
        string instead of actually sorting anything.

        The directory on disk is NOT renamed or moved — only the returned
        list is sorted. Callers can use the returned order to refresh a UI
        list or rename directories if they wish.
        """
        valid_by = {"name", "author"}
        if by not in valid_by:
            return {"success": False,
                    "message": f"Invalid sort key '{by}'; must be one of {sorted(valid_by)}"}

        if not themes_dir or not os.path.isdir(themes_dir):
            return {"success": False, "message": f"Themes directory not found: {themes_dir}"}

        entries: list[dict[str, Any]] = []
        unsortable: list[str] = []
        for entry in os.listdir(themes_dir):
            entry_path = os.path.join(themes_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            manifest_path = os.path.join(entry_path, "manifest.json")
            if not os.path.exists(manifest_path):
                unsortable.append(entry)
                continue
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Could not read manifest for %s: %s", entry, exc)
                unsortable.append(entry)
                continue
            entries.append({
                "name": manifest.get("name", entry),
                "author": manifest.get("author", ""),
                "version": manifest.get("version", ""),
                "dir": entry,
                "path": entry_path,
                "manifest": manifest,
            })

        # Sort by the requested key. Missing values sort to the bottom.
        entries.sort(key=lambda e: (e.get(by) or "", e.get("name", "")))

        # Append unsortable entries at the end so the caller sees them.
        for u in sorted(unsortable):
            entries.append({"name": u, "dir": u, "path": os.path.join(themes_dir, u),
                            "unsortable": True})

        return {
            "success": True,
            "by": by,
            "count": len(entries),
            "themes": entries,
        }

    def quarantine(self, pack_path: str, reason: str) -> str:
        """Move invalid pack to quarantine folder."""
        q_dir = os.path.join(os.path.dirname(pack_path), "quarantined")
        os.makedirs(q_dir, exist_ok=True)
        dest = os.path.join(q_dir, os.path.basename(pack_path))
        shutil.move(pack_path, dest)
        log.warning("Quarantined %s: %s", pack_path, reason)
        return dest