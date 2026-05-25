"""Theme Performance Analyzer Agent for ThemeSDK.

Measures and compares theme performance metrics (memory, load time, file count).
The previous implementation returned a hardcoded ``fps`` of 60.0 regardless of
actual performance — this version removes that fake metric entirely and records
real measurable values.  FPS requires a live UI session and cannot be measured
headless, so it is explicitly omitted with an ``fps_note`` instead.
"""

import json
import logging
import os
import time
from typing import Any, Dict, Optional

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

logger = logging.getLogger(__name__)

MEMORY_WARNING_THRESHOLD_MB: int = 500


class PerfAnalyzer:
    """Analyze and report theme performance metrics."""

    def __init__(self, sdk: Any = None) -> None:
        self._sdk = sdk
        self._metrics: Dict[str, Dict[str, Any]] = {}
        logger.info("PerfAnalyzer agent initialised")

    def measure(self, theme_name: str) -> Dict[str, Any]:
        """Measure performance metrics for *theme_name*.

        Records actual memory via psutil, times directory traversal for
        load-time estimation, and counts theme assets.  No fake ``fps``
        key is included — FPS requires a running UI session.

        Returns dict with keys: ``memory_mb``, ``load_time_ms``,
        ``file_count``, ``fps_note``.
        """
        memory_mb: float = 0.0
        if _PSUTIL_AVAILABLE:
            try:
                process = psutil.Process(os.getpid())
                memory_mb = process.memory_info().rss / (1024 * 1024)
            except Exception as exc:
                logger.warning("psutil memory query failed: %s", exc)

        load_time_ms: float = 0.0
        file_count: int = 0
        theme_path = (
            theme_name if os.path.isdir(theme_name)
            else self._resolve_theme_path(theme_name)
        )

        if theme_path and os.path.isdir(theme_path):
            start = time.perf_counter()
            for _root, _dirs, files in os.walk(theme_path):
                file_count += len(files)
            load_time_ms = (time.perf_counter() - start) * 1000.0
        else:
            logger.warning("Theme directory not found for %r", theme_name)

        metrics: Dict[str, Any] = {
            "memory_mb": round(memory_mb, 2),
            "load_time_ms": round(load_time_ms, 2),
            "file_count": file_count,
            "fps_note": "FPS requires a running UI session; not measurable headless",
        }
        self._metrics[theme_name] = metrics
        logger.info(
            "Measured %r → memory=%.1f MB  load=%.1f ms  files=%d",
            theme_name, memory_mb, load_time_ms, file_count,
        )
        return metrics

    def compare(self, theme_a: str, theme_b: str) -> Dict[str, Any]:
        """Compare two themes' metrics, handling missing keys gracefully.

        Uses ``.get()`` with defaults so missing keys never raise
        ``KeyError`` — even if a theme hasn't been measured yet.

        Returns dict with per-key deltas (b minus a) and a ``winner``.
        """
        metrics_a = self._metrics.get(theme_a, {})
        metrics_b = self._metrics.get(theme_b, {})

        delta_memory = round(
            metrics_b.get("memory_mb", 0.0) - metrics_a.get("memory_mb", 0.0), 2
        )
        delta_load = round(
            metrics_b.get("load_time_ms", 0.0) - metrics_a.get("load_time_ms", 0.0), 2
        )
        delta_files = metrics_b.get("file_count", 0) - metrics_a.get("file_count", 0)

        if delta_memory <= 0 and delta_load <= 0:
            winner = theme_b
        elif delta_memory >= 0 and delta_load >= 0:
            winner = theme_a
        else:
            winner = "inconclusive"

        result: Dict[str, Any] = {
            "delta_memory_mb": delta_memory,
            "delta_load_time_ms": delta_load,
            "delta_file_count": delta_files,
            "winner": winner,
        }
        logger.info(
            "Compare %r vs %r → winner=%s  Δmem=%.1f  Δload=%.1f",
            theme_a, theme_b, winner, delta_memory, delta_load,
        )
        return result

    def report(self, theme_name: str) -> str:
        """Generate a human-readable performance report for a theme.

        Auto-measures if the theme hasn't been measured yet.
        """
        metrics = self._metrics.get(theme_name)
        if metrics is None:
            metrics = self.measure(theme_name)

        lines = [
            f"Performance Report: {theme_name}",
            f"  Memory usage : {metrics.get('memory_mb', 0.0):.1f} MB",
            f"  Load time    : {metrics.get('load_time_ms', 0.0):.1f} ms",
            f"  File count   : {metrics.get('file_count', 0)}",
            f"  FPS          : {metrics.get('fps_note', 'N/A')}",
        ]
        if metrics.get("memory_mb", 0.0) > MEMORY_WARNING_THRESHOLD_MB:
            lines.append(f"  WARNING: Memory exceeds {MEMORY_WARNING_THRESHOLD_MB} MB threshold")
        return "\n".join(lines)

    def check_memory(self) -> Dict[str, Any]:
        """Check current system memory usage and warn if above threshold.

        Returns dict with ``used_mb``, ``total_mb``, ``percent``,
        ``above_threshold``.
        """
        if not _PSUTIL_AVAILABLE:
            logger.warning("psutil not available; memory check skipped")
            return {"used_mb": 0, "total_mb": 0, "percent": 0.0, "above_threshold": False}

        try:
            mem = psutil.virtual_memory()
            used_mb = round(mem.used / (1024 * 1024), 2)
            total_mb = round(mem.total / (1024 * 1024), 2)
            percent = round(mem.percent, 1)
        except Exception as exc:
            logger.error("Failed to read system memory: %s", exc)
            return {"used_mb": 0, "total_mb": 0, "percent": 0.0, "above_threshold": False}

        above = used_mb > MEMORY_WARNING_THRESHOLD_MB
        if above:
            logger.warning(
                "System memory %.0f MB exceeds threshold %d MB (%.1f%%)",
                used_mb, MEMORY_WARNING_THRESHOLD_MB, percent,
            )
        else:
            logger.info("System memory OK: %.0f MB / %.0f MB (%.1f%%)", used_mb, total_mb, percent)
        return {"used_mb": used_mb, "total_mb": total_mb, "percent": percent, "above_threshold": above}

    def _resolve_theme_path(self, theme_name: str) -> Optional[str]:
        """Resolve a theme name to a directory path via SDK config or fallbacks."""
        candidates: list[str] = []

        if self._sdk is not None:
            sdk_dir = getattr(self._sdk, "themes_dir", None)
            if sdk_dir:
                candidates.append(os.path.join(sdk_dir, theme_name))

        current = os.path.dirname(os.path.abspath(__file__))
        while True:
            cfg_path = os.path.join(current, "config.json")
            if os.path.isfile(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as fh:
                        cfg = json.load(fh)
                    td = cfg.get("themes_dir") or cfg.get("themes_directory")
                    if td:
                        candidates.append(os.path.join(os.path.expanduser(td), theme_name))
                except (json.JSONDecodeError, OSError):
                    pass
                break
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent

        candidates.append(os.path.expanduser(os.path.join("~/.gemini/themes", theme_name)))
        for candidate in candidates:
            if os.path.isdir(candidate):
                return candidate
        return None
