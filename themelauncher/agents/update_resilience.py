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
from typing import Any, Callable, Optional

try:
    import winreg  # Windows-only; module must import cleanly off-Windows.
except ImportError:  # pragma: no cover - non-Windows
    winreg = None

from ..core.logger import log


class UpdateResilience:
    """Monitor, detect, and auto-heal theme components broken by Windows Updates."""

    def __init__(self, theme_manager=None, snapshot_agent=None):
        self.theme_manager = theme_manager
        self.snapshot_agent = snapshot_agent
        self._running = False

    def stop(self) -> None:
        """Signal the ``watch_for_updates`` loop to exit at the next poll."""
        self._running = False
        log.info("Update watcher stop requested")

    def watch_for_updates(self, callback: Optional[Callable] = None) -> None:
        """Monitor Event Log for Windows Update completion events (Event ID 19).

        The callback (if supplied) is invoked for *notification* only. The
        agent itself ALWAYS calls ``_handle_update`` so the auto-heal path is
        reachable regardless of whether a callback is set (otherwise heal
        would never fire whenever the SDK supplies a default callback).
        """
        self._running = True
        log.info("Watching for Windows Update events...")

        # Simple polling approach: check event log periodically.
        while self._running:
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
                        # Always notify via callback (if provided) ...
                        if callback:
                            try:
                                callback(event_info)
                            except Exception:
                                log.exception("Update callback raised")
                        else:
                            log.info("Update detected: %s", event_info)
                        # ... and ALWAYS heal — never skip when a callback is set.
                        self._handle_update(event_info)
            except FileNotFoundError:
                # wevtutil is not present on this system (non-Windows or a
                # stripped image). Nothing to monitor — bail out cleanly.
                log.warning("wevtutil not found; cannot watch for Windows Update events")
                self._running = False
                return
            except Exception as exc:
                log.debug("Update check failed (non-critical): %s", exc)

            # Sleep 300s in 10s increments so we can exit promptly on stop().
            for _ in range(30):
                if not self._running:
                    return
                time.sleep(10)

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
        """Re-apply components that were overwritten by an update.

        Uses the injected ``snapshot_agent`` (the SDK wires one in via
        ``UpdateResilience(theme_manager, snapshot_agent)``) and restores ONCE
        rather than per-component — a single snapshot restore re-applies every
        component that the snapshot captured.
        """
        if not broken_components:
            return {"healed": [], "failed": []}

        snap = self.snapshot_agent
        if snap is None:
            # Fall back to a fresh SnapshotAgent only if none was injected.
            from ..agents.snapshot import SnapshotAgent
            snap = SnapshotAgent()

        if not (self.theme_manager and getattr(self.theme_manager, "active_theme", None)):
            log.warning("auto_heal: no active theme; cannot heal %s", broken_components)
            return {"healed": [], "failed": list(broken_components)}

        try:
            snap_result = snap.restore_snapshot()
        except Exception as exc:
            log.error("Snapshot restore raised while healing: %s", exc)
            return {"healed": [], "failed": list(broken_components)}

        if snap_result.get("success"):
            return {"healed": list(broken_components), "failed": []}
        return {"healed": [], "failed": list(broken_components)}

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