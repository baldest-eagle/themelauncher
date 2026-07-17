"""Crash Monitor Agent (Tier 2 - High Value). Structured error log analysis."""

import os
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from ..core.logger import LOG_DIR, log


def _project_root() -> str:
    """Return the project root directory (parent of the ``themelauncher`` package)."""
    # monitor.py → themelauncher/agents/monitor.py → up 3 levels = project root.
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class CrashMonitor:
    """Monitor, parse, and summarize runtime logs for error analysis.

    The SDK ships TWO log writers that write to DIFFERENT files:

    * ``themelauncher/core/logger.py``  →  ``$LOCALAPPDATA/logs/themelauncher.log``
      (the SDK log — this is where the agents + applier write via ``log.error``)
    * ``core/logger.py``                →  ``<project_root>/logs/theme_launcher.log``
      (the app/UI log — this is where the UI + main() write)

    Previously this agent only read the SDK log, so it never saw app/UI errors.
    Now it reads BOTH and tags each entry with the ``source`` it came from.
    """

    @staticmethod
    def _log_files() -> list[tuple[str, str]]:
        """Return ``[(source_name, path), ...]`` for every log file to scan."""
        files = [("sdk", os.path.join(LOG_DIR, "themelauncher.log"))]
        app_log = os.path.join(_project_root(), "logs", "theme_launcher.log")
        if app_log not in {p for _, p in files}:
            files.append(("app", app_log))
        return files

    @staticmethod
    def _parse_line(line: str) -> Optional[dict[str, str]]:
        """Parse a single log line into ``{timestamp, level, message}`` or None."""
        line = line.rstrip("\n")
        if "[ERROR]" not in line and "[CRITICAL]" not in line and "[WARNING]" not in line:
            # Only structured-level lines are interesting as "errors" here.
            if "[ERROR]" not in line and "[CRITICAL]" not in line:
                return None
        # Expected formats:
        #   SDK: "2024-01-01 12:34:56 [ERROR] message"
        #   app: "2024-01-01 12:34:56,123 [ERROR] message"  (logging default)
        parts = line.split(" ", 3)
        if len(parts) < 4:
            return None
        timestamp = parts[0] + " " + parts[1]
        level = parts[2].strip("[]")
        message = parts[3]
        return {"timestamp": timestamp, "level": level, "message": message}

    def get_errors(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent error entries as structured dicts.

        Reads BOTH the SDK log and the app log. Each returned entry includes a
        ``source`` field (``"sdk"`` or ``"app"``) so callers can disambiguate.
        """
        errors: list[dict[str, Any]] = []
        for source, log_file in self._log_files():
            if not os.path.exists(log_file):
                continue
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if "[ERROR]" not in line and "[CRITICAL]" not in line:
                            continue
                        parsed = self._parse_line(line)
                        if not parsed:
                            continue
                        parsed["source"] = source
                        errors.append(parsed)
                        if len(errors) >= limit:
                            return errors
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("Could not read log file %s: %s", log_file, exc)
        return errors

    def watch(self, callback: Callable, poll_interval: float = 5.0) -> None:
        """Real-time monitoring with callback for new errors.

        Polls all log files (SDK + app) so the caller is notified of errors
        from either source.
        """
        state = {}  # path -> last_size
        for _source, log_file in self._log_files():
            state[log_file] = os.path.getsize(log_file) if os.path.exists(log_file) else 0

        while True:
            time.sleep(poll_interval)
            for source, log_file in self._log_files():
                if not os.path.exists(log_file):
                    continue
                try:
                    new_size = os.path.getsize(log_file)
                except OSError:
                    continue
                last_size = state.get(log_file, 0)
                if new_size > last_size:
                    try:
                        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
                            f.seek(last_size)
                            for line in f:
                                if "[ERROR]" in line or "[CRITICAL]" in line:
                                    parsed = self._parse_line(line)
                                    if parsed:
                                        parsed["source"] = source
                                        callback(parsed)
                                    else:
                                        callback({"line": line.rstrip("\n"),
                                                  "source": source})
                    except Exception as exc:  # pragma: no cover - defensive
                        log.debug("watch read failed for %s: %s", log_file, exc)
                    state[log_file] = new_size

    def summarize(self, hours: int = 24) -> dict[str, Any]:
        """Aggregate error report for a time window.

        Actually filters by ``hours`` (parses each entry's timestamp and keeps
        only those within ``now - timedelta(hours=hours)``). Previously this
        ignored the parameter and reported all-time totals.
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        all_errors = self.get_errors(limit=10000)
        by_component: dict[str, int] = {}
        total = 0
        for err in all_errors:
            ts_str = err.get("timestamp", "")
            try:
                # SDK format: "2024-01-01 12:34:56"
                # app format may be "2024-01-01 12:34:56,123" — strip ms.
                ts_str_clean = ts_str.split(",")[0]
                ts = datetime.strptime(ts_str_clean, "%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                # If we can't parse the timestamp, keep it (don't silently drop).
                ts = datetime.now()
            if ts < cutoff:
                continue
            total += 1
            msg = err.get("message", "")
            for comp in ["cursors", "fonts", "msstyles", "terminal", "firefox",
                         "windhawk", "wallpaper", "icons", "themes"]:
                if comp in msg.lower():
                    by_component[comp] = by_component.get(comp, 0) + 1
                    break
        return {"total_errors": total, "by_component": by_component, "hours": hours}
