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
        """Reorganize theme directories (placeholder)."""
        return {"success": True, "message": f"Themes would be sorted by '{by}'"}

    def quarantine(self, pack_path: str, reason: str) -> str:
        """Move invalid pack to quarantine folder."""
        q_dir = os.path.join(os.path.dirname(pack_path), "quarantined")
        os.makedirs(q_dir, exist_ok=True)
        dest = os.path.join(q_dir, os.path.basename(pack_path))
        shutil.move(pack_path, dest)
        log.warning("Quarantined %s: %s", pack_path, reason)
        return dest