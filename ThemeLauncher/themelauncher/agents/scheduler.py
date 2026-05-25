"""Scheduled Theme Switcher Agent (Tier 3 - Enhancement). Cron-like theme rotation."""

import threading
import time
from datetime import datetime
from typing import Any, Callable, Optional

from ..core.logger import log


class ThemeScheduler:
    """Rotate themes on a cron-like schedule."""

    def __init__(self, apply_callback: Optional[Callable] = None):
        self._rules: dict[str, dict] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._apply_callback = apply_callback

    def add_rule(self, name: str, cron_expr: str, theme_name: str,
                 components: Optional[list[str]] = None) -> None:
        """Add a scheduled rule."""
        self._rules[name] = {
            "cron": cron_expr,
            "theme": theme_name,
            "components": components,
        }
        log.info("Schedule rule '%s' added: %s -> %s", name, cron_expr, theme_name)

    def remove_rule(self, name: str) -> bool:
        """Remove a scheduled rule."""
        return self._rules.pop(name, None) is not None

    def list_rules(self) -> list[dict[str, Any]]:
        """List all active rules."""
        return [{"name": k, **v} for k, v in self._rules.items()]

    def create_playlist(self, theme_names: list[str], interval_hours: int = 2) -> str:
        """Create a playlist that cycles through themes with staggered offsets.

        Instead of giving every theme the same cron (which would fire all at once),
        each theme gets a unique hour slot so they rotate sequentially through the
        day.  For example, with 3 themes and 2-hour intervals starting at the
        current hour:

          theme_0 fires at hour H+0   ->  "0 H * * *"
          theme_1 fires at hour H+2   ->  "0 H+2 * * *"
          theme_2 fires at hour H+4   ->  "0 H+4 * * *"

        Each fires once daily.  If the total span (interval * count) exceeds 24
        hours the hours wrap around via modulo 24 so the cycle repeats cleanly.

        Previous bug: the old code used ``% 60`` on a total-minute offset which
        discarded the hour component, causing themes to fire in the wrong order
        or at the wrong time.
        """
        playlist_name = f"playlist_{int(time.time())}"
        n = len(theme_names)
        if n == 0:
            return playlist_name

        # Use the current hour as the starting point so the first theme fires soon.
        base_hour = datetime.now().hour

        for i, theme in enumerate(theme_names):
            # Each theme gets its own hour slot, spaced by interval_hours.
            target_hour = (base_hour + i * interval_hours) % 24
            cron = f"0 {target_hour} * * *"
            self.add_rule(f"{playlist_name}_{i}", cron, theme)
        return playlist_name

    def start(self) -> None:
        """Start the scheduler in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info("Theme scheduler started")

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        log.info("Theme scheduler stopped")

    def _run(self) -> None:
        last_checked = None
        while self._running:
            now = datetime.now()
            minute_key = now.strftime("%H:%M")

            if minute_key != last_checked:
                last_checked = minute_key
                for name, rule in self._rules.items():
                    if self._matches_cron(rule["cron"], now):
                        log.info("Schedule triggered: %s -> %s", name, rule["theme"])
                        if self._apply_callback:
                            self._apply_callback(rule["theme"], rule.get("components"))

            time.sleep(30)

    def _matches_cron(self, cron_expr: str, dt: datetime) -> bool:
        """Robust cron matching for standard patterns (minute, hour, day, month, day_of_week)."""
        parts = cron_expr.split()
        if len(parts) < 2:
            return False

        # Support full 5-field cron format: min, hour, day, month, day_of_week
        # Pad with * if only 2 fields are supplied
        while len(parts) < 5:
            parts.append("*")

        min_expr, hour_expr, dom_expr, month_expr, dow_expr = parts[:5]

        def match_field(val: int, expr: str) -> bool:
            if expr == "*":
                return True
            # Handle list (e.g., "1,3,5")
            if "," in expr:
                return any(match_field(val, sub) for sub in expr.split(","))
            # Handle step (e.g., "*/2", "1-5/2")
            step = 1
            if "/" in expr:
                expr, step_str = expr.split("/", 1)
                try:
                    step = int(step_str)
                except ValueError:
                    return False
            # Handle range (e.g., "1-5")
            if "-" in expr:
                start_str, end_str = expr.split("-", 1)
                try:
                    start, end = int(start_str), int(end_str)
                    return start <= val <= end and (val - start) % step == 0
                except ValueError:
                    return False
            # Handle simple step "*/2" where left is "*"
            if expr == "*":
                return val % step == 0
            # Handle exact digit
            if expr.isdigit():
                try:
                    num = int(expr)
                    return val == num and val % step == 0
                except ValueError:
                    return False
            return False

        # Day of week in cron: 0 or 7 is Sunday, 1 is Monday, etc.
        # dt.isoweekday() returns 1 (Monday) to 7 (Sunday)
        dow_val = dt.isoweekday()
        if dow_val == 7:
            dow_val = 0  # Normalize Sunday to 0 to match standard cron

        return (
            match_field(dt.minute, min_expr) and
            match_field(dt.hour, hour_expr) and
            match_field(dt.day, dom_expr) and
            match_field(dt.month, month_expr) and
            match_field(dow_val, dow_expr)
        )
