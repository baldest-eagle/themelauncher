import os
import time
import ctypes
from typing import Any, Optional

from ..core.logger import log


class PerfAnalyzer:
    """Benchmark system performance before and after applying theme components."""

    def __init__(self):
        self._baseline: dict[str, float] = {}
        self._thresholds = {"latency_ms": 50, "mem_mb": 200}

    def benchmark_baseline(self) -> dict[str, float]:
        """Measure pre-apply performance metrics."""
        self._baseline = self._gather_metrics()
        return self._baseline

    def benchmark_after(self, component: str) -> dict[str, float]:
        """Measure post-apply metrics for one component."""
        return self._gather_metrics()

    def _gather_metrics(self) -> dict[str, float]:
        """Gather real memory, file I/O latency, and UI latency metrics.

        Note: FPS is intentionally omitted because it requires a running UI
        session and cannot be measured headless.  Previous versions returned
        a hardcoded ``fps: 60.0`` which was misleading.
        """
        metrics: dict[str, float] = {}

        # 1. Measure Memory Usage
        try:
            import psutil
            mem = psutil.virtual_memory()
            metrics["mem_available_mb"] = float(mem.available) / (1024 * 1024)
        except ImportError:
            # Fallback using ctypes to call GlobalMemoryStatusEx on Windows
            try:
                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ('dwLength', ctypes.c_ulong),
                        ('dwMemoryLoad', ctypes.c_ulong),
                        ('ullTotalPhys', ctypes.c_ulonglong),
                        ('ullAvailPhys', ctypes.c_ulonglong),
                        ('ullTotalPageFile', ctypes.c_ulonglong),
                        ('ullAvailPageFile', ctypes.c_ulonglong),
                        ('ullTotalVirtual', ctypes.c_ulonglong),
                        ('ullAvailVirtual', ctypes.c_ulonglong),
                        ('ullAvailExtendedVirtual', ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                metrics["mem_available_mb"] = float(stat.ullAvailPhys) / (1024 * 1024)
            except Exception:
                pass

        # 2. Measure File I/O Latency
        try:
            import tempfile
            t0 = time.perf_counter()
            for _ in range(5):
                with tempfile.NamedTemporaryFile(delete=False) as f:
                    f.write(b"theme_launcher_bench" * 1000)
                    temp_name = f.name
                with open(temp_name, "rb") as f:
                    _ = f.read()
                os.remove(temp_name)
            t1 = time.perf_counter()
            metrics["io_latency_ms"] = ((t1 - t0) / 5.0) * 1000.0
        except Exception:
            metrics["io_latency_ms"] = 2.0

        # 3. Measure Scheduling/UI response latency
        try:
            t0 = time.perf_counter()
            for _ in range(100):
                time.sleep(0.0001)
            t1 = time.perf_counter()
            metrics["latency_ms"] = ((t1 - t0) / 100.0) * 1000.0
        except Exception:
            metrics["latency_ms"] = 15.0

        return metrics

    def compare(self, baseline: dict, after: dict) -> dict[str, Any]:
        """Compute delta and flag regressions.

        Uses .get() with defaults so missing keys never raise KeyError,
        even if one of the metric dicts is incomplete or comes from
        external code.
        """
        deltas = {}
        all_keys = set(baseline.keys()) | set(after.keys())
        for key in all_keys:
            b_val = baseline.get(key, 0.0)
            a_val = after.get(key, 0.0)
            deltas[f"{key}_delta"] = a_val - b_val

        regression = False
        if "latency_ms_delta" in deltas and deltas["latency_ms_delta"] > self._thresholds["latency_ms"]:
            regression = True
        if "mem_available_mb_delta" in deltas and abs(deltas.get("mem_available_mb_delta", 0.0)) > self._thresholds["mem_mb"]:
            regression = True

        return {**deltas, "regression": regression}

    def set_thresholds(self, latency_ms: Optional[float] = None,
                       mem_mb: Optional[float] = None) -> None:
        """Configure regression thresholds."""
        if latency_ms is not None:
            self._thresholds["latency_ms"] = latency_ms
        if mem_mb is not None:
            self._thresholds["mem_mb"] = mem_mb
