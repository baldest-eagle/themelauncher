"""Crash Monitor Agent (Tier 2 - High Value). Structured error log analysis."""

import json
import os
import time
from typing import Any, Callable, Optional

from ..core.logger import LOG_DIR, log


class CrashMonitor:
    """Monitor, parse, and summarize the SDK runtime log for error analysis."""

    def __init__(self):
        self._stop_watching = False

    def stop_watching(self) -> None:
        """Signal the real-time monitor to stop watching."""
        self._stop_watching = True

    def get_errors(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent error entries as structured dicts."""
        log_file = os.path.join(LOG_DIR, "themelauncher.log")
        if not os.path.exists(log_file):
            return []

        errors = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if "[ERROR]" in line or "[CRITICAL]" in line:
                    parts = line.strip().split(" ", 3)
                    errors.append({
                        "timestamp": parts[0] + " " + parts[1] if len(parts) >= 2 else "",
                        "level": parts[2].strip("[]") if len(parts) >= 3 else "",
                        "message": parts[3] if len(parts) >= 4 else line.strip(),
                    })
                    if len(errors) >= limit:
                        break
        return errors

    def watch(self, callback: Callable, poll_interval: float = 5.0) -> None:
        """Real-time monitoring with callback for new errors."""
        self._stop_watching = False
        log_file = os.path.join(LOG_DIR, "themelauncher.log")
        last_size = os.path.getsize(log_file) if os.path.exists(log_file) else 0

        while not self._stop_watching:
            time.sleep(poll_interval)
            if os.path.exists(log_file):
                new_size = os.path.getsize(log_file)
                if new_size < last_size:
                    # Log file was rotated or truncated
                    last_size = 0
                if new_size > last_size:
                    with open(log_file, "r", encoding="utf-8") as f:
                        f.seek(last_size)
                        for line in f:
                            if "[ERROR]" in line or "[CRITICAL]" in line:
                                parts = line.strip().split(" ", 3)
                                callback({
                                    "line": line.strip(),
                                    "timestamp": parts[0] + " " + parts[1] if len(parts) >= 2 else "",
                                    "level": parts[2].strip("[]") if len(parts) >= 3 else "ERROR",
                                    "message": parts[3] if len(parts) >= 4 else line.strip(),
                                })
                    last_size = new_size

    def summarize(self, hours: int = 24) -> dict[str, Any]:
        """Aggregate error report for a time window."""
        errors = self.get_errors(limit=1000)
        by_component: dict[str, int] = {}
        for err in errors:
            msg = err.get("message", "")
            for comp in ["cursors", "fonts", "msstyles", "terminal", "firefox",
                         "windhawk", "wallpaper", "icons", "themes"]:
                if comp in msg.lower():
                    by_component[comp] = by_component.get(comp, 0) + 1
                    break
        return {"total_errors": len(errors), "by_component": by_component}