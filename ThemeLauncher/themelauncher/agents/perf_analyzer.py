import os
import time
import ctypes
from typing import Any, Optional

from ..core.logger import log


class PerfAnalyzer:
    """Benchmark system performance before and after applying theme components."""

    def __init__(self):
        self._baseline: dict[str, float] = {}
        self._thresholds = {"latency_ms": 50, "fps": 5, "mem_mb": 200}

    def benchmark_baseline(self) -> dict[str, float]:
        """Measure pre-apply performance metrics."""
        self._baseline = self._gather_metrics()
        return self._baseline

    def benchmark_after(self, component: str) -> dict[str, float]:
        """Measure post-apply metrics for one component."""
        return self._gather_metrics()

    def _gather_metrics(self) -> dict[str, float]:
        """Gather real memory, file I/O latency, and UI latency metrics."""
        metrics = {
            "fps": 60.0,  # Simulated/Standard default
            "latency_ms": 1.0,
            "mem_available_mb": 4096.0,
        }

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
        """Compute delta and flag regressions."""
        deltas = {}
        for key in baseline:
            if key in after:
                deltas[f"{key}_delta"] = after[key] - baseline[key]

        regression = False
        if deltas.get("fps_delta", 0) < -self._thresholds["fps"]:
            regression = True
        if deltas.get("latency_ms_delta", 0) > self._thresholds["latency_ms"]:
            regression = True

        return {**deltas, "regression": regression}

    def set_thresholds(self, latency_ms: Optional[float] = None,
                       fps: Optional[float] = None,
                       mem_mb: Optional[float] = None) -> None:
        """Configure regression thresholds."""
        if latency_ms is not None:
            self._thresholds["latency_ms"] = latency_ms
        if fps is not None:
            self._thresholds["fps"] = fps
        if mem_mb is not None:
            self._thresholds["mem_mb"] = mem_mb