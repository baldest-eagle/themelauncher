"""
Crash-safe I/O helpers for ThemeLauncher.

Provides atomic file writes (temp + os.replace), safe removal that swallows
common Windows errors, and retry-with-backoff wrappers for transient sharing
violations. Used across core/ to eliminate the truncate-then-write corruption
class of bugs (config.json, icon_sets.json, manifest.json, terminal settings).
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
from typing import Any, Callable, Iterable, TypeVar

from core.logger import log

T = TypeVar("T")


def atomic_write(path: str, data: str | bytes, *, encoding: str = "utf-8") -> None:
    """Write ``data`` to ``path`` atomically.

    Writes to a temporary file in the same directory (so os.replace is atomic
    on the same filesystem), fsyncs it, then os.replaces into place. Cleans
    up the temp file on any failure.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp_", suffix=os.path.basename(path))
    try:
        with os.fdopen(fd, "wb") as f:
            if isinstance(data, str):
                f.write(data.encode(encoding))
            else:
                f.write(data)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError as exc:
                log.debug("atomic_write: fsync failed (non-fatal): %s", exc)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up the temp file on any failure
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def atomic_write_json(path: str, obj: Any, *, indent: int = 2, encoding: str = "utf-8") -> None:
    """Serialize ``obj`` as JSON and write atomically to ``path``."""
    data = json.dumps(obj, indent=indent, ensure_ascii=False)
    atomic_write(path, data, encoding=encoding)


def safe_remove(path: str, *, log_missing: bool = False) -> bool:
    """Remove a file, swallowing FileNotFoundError.

    Returns True if the file is gone afterwards (either removed or already
    missing). Other OS errors are logged at warning level and we return False.
    """
    try:
        os.remove(path)
        return True
    except FileNotFoundError:
        if log_missing:
            log.debug("safe_remove: already gone: %s", path)
        return True
    except OSError as exc:
        log.warning("safe_remove: could not remove %s: %s", path, exc)
        return False


def retry(
    fn: Callable[[], T],
    *,
    tries: int = 3,
    delays: Iterable[float] = (0.05, 0.2, 0.8),
) -> T:
    """Run ``fn`` with exponential backoff for transient Windows errors.

    Retries on PermissionError or OSError (the typical signals of a Windows
    sharing violation: another process has the file open). Any other exception
    propagates immediately.
    """
    delay_list = list(delays)
    last_exc: Exception | None = None
    for attempt in range(tries):
        try:
            return fn()
        except (PermissionError, OSError) as exc:
            last_exc = exc
            if attempt + 1 >= tries:
                break
            delay = delay_list[min(attempt, len(delay_list) - 1)]
            log.debug("retry: attempt %d failed (%s); sleeping %.3fs", attempt + 1, exc, delay)
            time.sleep(delay)
    assert last_exc is not None  # narrow type: only reached if we retried
    raise last_exc


def copy_with_retry(src: str, dst: str, *, tries: int = 3) -> str:
    """shutil.copy2 wrapped in :func:`retry` for transient sharing violations."""
    return retry(lambda: shutil.copy2(src, dst), tries=tries)
