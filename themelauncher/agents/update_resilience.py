"""
Windows Update Resilience Monitor Agent (Tier 1 - Critical).

Monitors for Windows Update events, verifies whether applied theme components
are still intact after an update, and automatically re-applies any that were overwritten.
"""

import ctypes
import json
import os
import shutil
import subprocess
import time
import winreg
from typing import Any, Callable, Optional

from ..core.logger import log


class UpdateResilience:
    """Monitor, detect, and auto-heal theme components broken by Windows Updates."""

    def __init__(self, theme_manager=None, snapshot_agent=None):
        self.theme_manager = theme_manager
        self.snapshot_agent = snapshot_agent

    def watch_for_updates(self, callback: Optional[Callable] = None) -> None:
        """Monitor Event Log for Windows Update completion events (Event ID 19)."""
        log.info("Watching for Windows Update events...")

        # Simple polling approach: check event log periodically
        last_check = time.time()
        while True:
            try:
                result = subprocess.run(
                    ["wevtutil", "qe", "Microsoft-Windows-WindowsUpdateClient/Operational",
                     "/q:", "*[System[EventID=19]]", "/rd:true", "/c:1", "/e:false"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    lines = result.stdout.strip().split("\n")
                    event_info = self._parse_update_event(lines)
                    if event_info:
                        if callback:
                            callback(event_info)
                        else:
                            log.info("Update detected: %s", event_info)
                            self._handle_update(event_info)
            except Exception as exc:
                log.debug("Update check failed (non-critical): %s", exc)

            time.sleep(300)  # Check every 5 minutes

    def _parse_update_event(self, lines: list[str]) -> Optional[dict]:
        """Extract KB number from event log text."""
        for line in lines:
            if "KB" in line:
                import re
                match = re.search(r'KB\d+', line)
                if match:
                    return {"kb": match.group(0)}
        return None

    def check_integrity(self) -> dict[str, Any]:
        """Compare current system state vs expected state, return broken components."""
        result: dict[str, Any] = {"intact": [], "broken": [], "unknown": []}

        # Check wallpaper
        try:
            buf = ctypes.create_unicode_buffer(260)
            ctypes.windll.user32.SystemParametersInfoW(0x0073, 260, buf, 0)
            wallpaper = buf.value
            if wallpaper and os.path.exists(wallpaper):
                result["intact"].append("wallpaper")
            else:
                result["broken"].append("wallpaper")
        except Exception:
            result["unknown"].append("wallpaper")

        # Check cursors
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0, winreg.KEY_READ
            )
            scheme_source, _ = winreg.QueryValueEx(key, "Scheme Source")
            winreg.CloseKey(key)
            if scheme_source == 1:
                result["intact"].append("cursors")
            else:
                result["broken"].append("cursors")
        except Exception:
            result["unknown"].append("cursors")

        # Check windhawk mods
        windhawk_path = os.path.join(
            os.environ.get("APPDATA", ""), "Windhawk", "ModsWritable"
        )
        if os.path.isdir(windhawk_path) and os.listdir(windhawk_path):
            result["intact"].append("windhawk")
        else:
            result["unknown"].append("windhawk")

        return result

    def auto_heal(self, broken_components: list[str]) -> dict[str, Any]:
        """Re-apply components that were overwritten by an update."""
        healed = []
        failed = []

        for component in broken_components:
            try:
                if self.theme_manager and self.theme_manager.active_theme:
                    from ..agents.snapshot import SnapshotAgent
                    snap = SnapshotAgent()
                    # Restore from snapshot
                    snap_result = snap.restore_snapshot()
                    if snap_result.get("success"):
                        healed.append(component)
                    else:
                        failed.append(component)
                else:
                    failed.append(component)
            except Exception as exc:
                log.error("Failed to heal %s: %s", component, exc)
                failed.append(component)

        return {"healed": healed, "failed": failed}

    def schedule_post_update_check(self) -> None:
        """Register a one-shot task for next boot via schtasks."""
        try:
            script = __file__
            subprocess.run(
                ["schtasks", "/create", "/tn", "ThemeLauncher_UpdateCheck",
                 "/tr", f'python "{script}"', "/sc", "onstart",
                 "/f", "/it"],
                check=False,
            )
            log.info("Scheduled post-update integrity check")
        except Exception as exc:
            log.warning("Could not schedule update check: %s", exc)

    def _handle_update(self, event: dict) -> None:
        """Handle a detected update by checking and healing if needed."""
        log.info("Windows update %s detected — checking integrity...", event.get("kb"))
        integrity = self.check_integrity()
        if integrity["broken"]:
            log.warning("Components broken by update: %s", integrity["broken"])
            result = self.auto_heal(integrity["broken"])
            log.info("Healed: %s, Failed: %s", result["healed"], result["failed"])
        else:
            log.info("All theme components intact after update")