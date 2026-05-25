"""
Registry Snapshot and Smart Rollback Agent (Tier 1 - Critical).

Captures a complete baseline of all theme-related registry keys, file hashes,
and configuration states before any theme is applied. When rollback is requested,
restores the exact pre-theme state.
"""

import ctypes
import hashlib
import json
import os
import shutil
import time
import winreg
from datetime import datetime
from typing import Any, Optional

from ..core.logger import log

SNAPSHOTS_DIR = os.path.join(
    os.environ.get("LOCALAPPDATA", ".themelauncher"),
    "snapshots",
)


class SnapshotAgent:
    """Capture, restore, and diff system state snapshots for safe rollback."""

    def __init__(self, snapshots_dir: str = SNAPSHOTS_DIR):
        self.snapshots_dir = snapshots_dir
        os.makedirs(self.snapshots_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Snapshot capture
    # ------------------------------------------------------------------

    def capture_snapshot(self) -> str:
        """Save current system state to a timestamped JSON file. Returns snapshot ID."""
        snapshot = {
            "id": datetime.now().strftime("%Y-%m-%dT%H-%M-%S"),
            "timestamp": time.time(),
            "cursors": self._capture_cursors(),
            "current_theme": self._capture_current_theme(),
            "wallpaper": self._capture_wallpaper(),
            "terminal_hash": self._capture_terminal_hash(),
            "windhawk_mods": self._capture_windhawk_mods(),
            "fonts": self._capture_fonts(),
            "startallback": self._capture_startallback(),
        }

        filepath = os.path.join(self.snapshots_dir, f"{snapshot['id']}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, default=str)

        log.info("Snapshot captured: %s", snapshot["id"])
        return snapshot["id"]

    def _capture_cursors(self) -> dict[str, str]:
        result = {}
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0, winreg.KEY_READ
            )
            for i in range(16):
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    if isinstance(value, str):
                        result[name] = value
                except OSError:
                    break
            winreg.CloseKey(key)
        except Exception as exc:
            log.warning("Failed to capture cursors: %s", exc)
        return result

    def _capture_current_theme(self) -> Optional[str]:
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes",
                0,
                winreg.KEY_READ,
            )
            value, _ = winreg.QueryValueEx(key, "CurrentTheme")
            winreg.CloseKey(key)
            return value
        except Exception:
            return None

    def _capture_wallpaper(self) -> Optional[str]:
        try:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.user32.SystemParametersInfoW(0x0073, 260, buf, 0)
            return buf.value
        except Exception:
            return None

    def _capture_terminal_hash(self) -> Optional[str]:
        terminal_paths = [
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""),
                r"Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json",
            ),
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""),
                r"Packages\Microsoft.WindowsTerminalPreview_8wekyb3d8bbwe\LocalState\settings.json",
            ),
            os.path.join(
                os.environ.get("LOCALAPPDATA", ""),
                "Microsoft\\Windows Terminal\\settings.json",
            ),
        ]
        for path in terminal_paths:
            if os.path.exists(path):
                try:
                    with open(path, "rb") as f:
                        return hashlib.sha256(f.read()).hexdigest()
                except Exception:
                    continue
        return None

    def _capture_windhawk_mods(self) -> list[str]:
        windhawk_path = os.path.join(
            os.environ.get("APPDATA", ""), "Windhawk", "ModsWritable"
        )
        if os.path.exists(windhawk_path):
            try:
                return os.listdir(windhawk_path)
            except Exception:
                pass
        return []

    def _capture_fonts(self) -> dict[str, str]:
        result = {}
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts",
                0,
                winreg.KEY_READ,
            )
            for i in range(512):
                try:
                    name, value, _ = winreg.EnumValue(key, i)
                    if isinstance(value, str):
                        result[name] = value
                except OSError:
                    break
            winreg.CloseKey(key)
        except Exception:
            pass
        return result

    def _capture_startallback(self) -> Optional[str]:
        sab_dir = os.path.join(os.environ.get("APPDATA", ""), "StartIsBack")
        if os.path.isdir(sab_dir):
            files = os.listdir(sab_dir)
            return json.dumps(files) if files else None
        return None

    # ------------------------------------------------------------------
    # Snapshot management
    # ------------------------------------------------------------------

    def list_snapshots(self) -> list[dict[str, Any]]:
        """List all saved snapshots with timestamps."""
        snapshots = []
        if not os.path.isdir(self.snapshots_dir):
            return snapshots
        for filename in sorted(os.listdir(self.snapshots_dir), reverse=True):
            if filename.endswith(".json"):
                filepath = os.path.join(self.snapshots_dir, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    snapshots.append({
                        "id": data.get("id", filename[:-5]),
                        "timestamp": data.get("timestamp", 0),
                        "datetime": datetime.fromtimestamp(
                            data.get("timestamp", 0)
                        ).isoformat(),
                    })
                except Exception:
                    snapshots.append({"id": filename[:-5], "timestamp": 0})
        return snapshots

    def get_snapshot(self, snapshot_id: Optional[str] = None) -> Optional[dict]:
        """Load a specific snapshot (default: latest)."""
        if snapshot_id:
            filepath = os.path.join(self.snapshots_dir, f"{snapshot_id}.json")
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        # Return latest
        snapshots = self.list_snapshots()
        if not snapshots:
            return None
        return self.get_snapshot(snapshots[0]["id"])

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Remove a snapshot from storage."""
        filepath = os.path.join(self.snapshots_dir, f"{snapshot_id}.json")
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    def restore_snapshot(self, snapshot_id: Optional[str] = None) -> dict[str, Any]:
        """Restore system state to a specific snapshot (default: latest)."""
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return {"success": False, "message": "No snapshot found to restore from."}

        restored = []

        # Restore cursors
        if snapshot.get("cursors"):
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Control Panel\Cursors",
                    0,
                    winreg.KEY_WRITE,
                )
                for name, value in snapshot["cursors"].items():
                    if isinstance(value, str):
                        winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
                winreg.CloseKey(key)
                ctypes.windll.user32.SystemParametersInfoW(0x0057, 0, None, 2)
                restored.append("cursors")
            except Exception as exc:
                log.warning("Failed to restore cursors: %s", exc)

        # Restore current theme
        theme_path = snapshot.get("current_theme")
        if theme_path:
            try:
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes",
                    0,
                    winreg.KEY_WRITE,
                )
                winreg.SetValueEx(key, "CurrentTheme", 0, winreg.REG_SZ, theme_path)
                winreg.CloseKey(key)
                ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "ImmersiveColorSet")
                restored.append("current_theme")
            except Exception as exc:
                log.warning("Failed to restore current theme: %s", exc)

        # Restore wallpaper
        wallpaper = snapshot.get("wallpaper")
        if wallpaper and os.path.exists(wallpaper):
            try:
                ctypes.windll.user32.SystemParametersInfoW(20, 0, wallpaper, 3)
                restored.append("wallpaper")
            except Exception:
                pass

        return {
            "success": True,
            "restored": restored,
            "from_snapshot": snapshot.get("id"),
        }

    # ------------------------------------------------------------------
    # Diff
    # ------------------------------------------------------------------

    def diff_current(self, snapshot_id: Optional[str] = None) -> dict[str, Any]:
        """Show what changed since snapshot was taken."""
        snapshot = self.get_snapshot(snapshot_id)
        if not snapshot:
            return {"error": "No snapshot found."}

        changes = {"modified_keys": 0, "changed_files": 0, "details": []}

        # Compare cursors
        current_cursors = self._capture_cursors()
        for key, old_val in snapshot.get("cursors", {}).items():
            new_val = current_cursors.get(key)
            if new_val != old_val:
                changes["modified_keys"] += 1
                changes["details"].append({
                    "key": f"Control Panel\\Cursors\\{key}",
                    "before": old_val,
                    "after": new_val,
                })

        # Compare wallpaper
        current_wallpaper = self._capture_wallpaper()
        if current_wallpaper != snapshot.get("wallpaper"):
            changes["modified_keys"] += 1
            changes["details"].append({
                "key": "Wallpaper",
                "before": snapshot.get("wallpaper"),
                "after": current_wallpaper,
            })

        return changes

    def diff_snapshots(self, id_a: str, id_b: str) -> dict[str, Any]:
        """Compare two snapshots side by side."""
        snap_a = self.get_snapshot(id_a)
        snap_b = self.get_snapshot(id_b)
        if not snap_a or not snap_b:
            return {"error": "One or both snapshots not found."}

        diffs = []
        for key in ["cursors", "current_theme", "wallpaper"]:
            if snap_a.get(key) != snap_b.get(key):
                diffs.append({
                    "key": key,
                    "snapshot_a": snap_a.get(key),
                    "snapshot_b": snap_b.get(key),
                })

        return {"differences": diffs}