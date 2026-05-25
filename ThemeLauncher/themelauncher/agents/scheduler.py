"""Theme Scheduling Agent for ThemeSDK.

Manages theme schedules and playlists with staggered cron expressions so that
themes in a playlist rotate sequentially instead of firing simultaneously.

The key fix over the previous implementation: :meth:`create_playlist` now
offsets each theme's cron expression by *interval_minutes* from the previous
one, producing individual ``minute hour day month day_of_week`` fields that
reflect the actual wall-clock time each theme should activate.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Minimum number of fields in a valid cron expression (standard 5-field format).
_CRON_FIELD_COUNT = 5


def _validate_cron(expr: str) -> bool:
    """Return ``True`` if *expr* looks like a valid 5-field cron string.

    This is a lightweight sanity check — it ensures five whitespace-separated
    tokens exist and that the first two (minute, hour) are numeric or ``*``.
    It does **not** attempt full cron grammar validation.
    """
    parts = expr.strip().split()
    if len(parts) != _CRON_FIELD_COUNT:
        return False
    for field in parts[:2]:  # minute, hour
        if field == "*":
            continue
        try:
            int(field)
        except ValueError:
            return False
    return True


class Scheduler:
    """Schedule themes and manage playlists with staggered activation times.

    Parameters
    ----------
    sdk : Any
        Reference to the parent ThemeSDK instance (stored but not yet used
        for dispatch; reserved for future callback integration).
    """

    def __init__(self, sdk: Any = None) -> None:
        self._sdk = sdk
        self._schedules: Dict[str, Dict[str, str]] = {}
        logger.info("Scheduler agent initialised")

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def schedule_theme(self, name: str, cron_expr: str) -> Dict[str, str]:
        """Schedule a single theme at the given cron time.

        Parameters
        ----------
        name : str
            Unique identifier for the theme.
        cron_expr : str
            A standard 5-field cron expression (minute hour day month dow).

        Returns
        -------
        dict
            ``{"name": name, "cron": cron_expr}``

        Raises
        ------
        ValueError
            If *cron_expr* is not a valid 5-field expression.
        """
        if not _validate_cron(cron_expr):
            logger.error("Invalid cron expression for %r: %s", name, cron_expr)
            raise ValueError(f"Invalid cron expression: {cron_expr!r}")

        self._schedules[name] = {"name": name, "cron": cron_expr}
        logger.info("Scheduled theme %r at %s", name, cron_expr)
        return self._schedules[name]

    def create_playlist(
        self,
        names: List[str],
        interval_minutes: int = 60,
        start_time: Optional[datetime] = None,
    ) -> List[Dict[str, str]]:
        """Create a staggered playlist of theme schedule entries.

        Each theme fires *interval_minutes* after the previous one.  For
        example, with three themes starting at 09:00 and a 60-minute
        interval::

            theme[0] → "0 9 * * *"
            theme[1] → "0 10 * * *"
            theme[2] → "0 11 * * *"

        Parameters
        ----------
        names : list[str]
            Theme names to include in the playlist.
        interval_minutes : int
            Minutes between successive theme activations (default 60).
        start_time : datetime or None
            When the first theme should fire.  Defaults to the start of the
            current hour (i.e. minute=0 of the current hour).

        Returns
        -------
        list[dict]
            Each dict has ``"name"`` and ``"cron"`` keys.

        Raises
        ------
        ValueError
            If *names* is empty or *interval_minutes* is not positive.
        """
        if not names:
            raise ValueError("Playlist must contain at least one theme")
        if interval_minutes <= 0:
            raise ValueError("interval_minutes must be a positive integer")

        if start_time is None:
            start_time = datetime.now().replace(minute=0, second=0, microsecond=0)

        base_minute = start_time.minute
        base_hour = start_time.hour
        playlist: List[Dict[str, str]] = []

        for idx, name in enumerate(names):
            total_offset = idx * interval_minutes
            target_hour = base_hour + (base_minute + total_offset) // 60
            target_minute = (base_minute + total_offset) % 60
            # Wrap hours into 0–23 for a daily cron cycle
            target_hour = target_hour % 24

            cron_expr = f"{target_minute} {target_hour} * * *"
            self._schedules[name] = {"name": name, "cron": cron_expr}
            playlist.append(self._schedules[name])
            logger.info(
                "Playlist entry %d: theme %r → cron %s", idx, name, cron_expr
            )

        logger.info(
            "Created playlist of %d theme(s) with %d-min interval",
            len(playlist),
            interval_minutes,
        )
        return playlist

    def remove_schedule(self, name: str) -> bool:
        """Remove a theme from the schedule.

        Returns ``True`` if the theme was found and removed, ``False``
        otherwise.
        """
        if name in self._schedules:
            del self._schedules[name]
            logger.info("Removed schedule for theme %r", name)
            return True
        logger.warning("No schedule found for theme %r", name)
        return False

    def list_schedules(self) -> List[Dict[str, str]]:
        """Return all current schedule entries as a list of dicts."""
        return list(self._schedules.values())

    # ------------------------------------------------------------------
    # Helper
    # ------------------------------------------------------------------

    def get_next_theme(self) -> Optional[Dict[str, str]]:
        """Return the theme scheduled to fire next based on current time.

        Compares each schedule's hour and minute against the current
        wall-clock time and returns the entry whose activation time is
        closest in the future.  If no future activation exists today
        (i.e. all are in the past), the earliest entry of the day wraps
        around and is returned.

        Returns ``None`` when the schedule is empty.
        """
        if not self._schedules:
            logger.debug("No schedules available")
            return None

        now = datetime.now()
        now_minutes = now.hour * 60 + now.minute

        best: Optional[Dict[str, str]] = None
        best_delta: Optional[int] = None

        for entry in self._schedules.values():
            parts = entry["cron"].split()
            if len(parts) < 2 or parts[0] == "*" or parts[1] == "*":
                continue
            try:
                entry_min = int(parts[0])
                entry_hr = int(parts[1])
            except ValueError:
                continue

            entry_minutes = entry_hr * 60 + entry_min
            # Positive delta means the entry is in the future today
            delta = entry_minutes - now_minutes
            # Wrap: if in the past, treat as tomorrow (+1440 minutes)
            if delta < 0:
                delta += 24 * 60

            if best_delta is None or delta < best_delta:
                best_delta = delta
                best = entry

        if best is not None:
            logger.debug("Next theme: %r at %s", best["name"], best["cron"])
        return best
