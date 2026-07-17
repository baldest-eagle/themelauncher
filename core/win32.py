"""
Centralized Windows API shim for ThemeLauncher.

Lazy-imports ``winreg`` and provides:
- :class:`_RegKeyContext` — context manager that guarantees CloseKey in finally
- :func:`reg_open_key` — open a registry key as a context manager
- :func:`reg_set_value` — SetValueEx with auto-inferred type
- :func:`set_system_parameter` — SystemParametersInfoW with return-code check
- :func:`require_windows` — clear error message on non-Windows

The rest of core/ imports cleanly on any OS thanks to this shim.
"""

from __future__ import annotations

import ctypes
import sys
from typing import Any

from core.logger import log

is_windows = sys.platform == "win32"

_winreg: Any = None


def _ensure_winreg() -> Any:
    """Lazy-import winreg; returns None on non-Windows."""
    global _winreg
    if _winreg is not None:
        return _winreg
    try:
        import winreg as _w  # type: ignore[import-not-found]
        _winreg = _w
    except ImportError:
        _winreg = None
    return _winreg


# Eagerly resolve on import so is_windows / _winreg are consistent at first use.
if is_windows:
    _ensure_winreg()


class _RegKeyContext:
    """Context manager wrapping a registry HKEY handle.

    Guarantees CloseKey in __exit__ even if SetValueEx raises.
    """

    def __init__(self, key: Any):
        self._key = key

    def __enter__(self) -> Any:
        return self._key

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._key is not None:
            try:
                _ensure_winreg().CloseKey(self._key)
            except Exception as close_exc:  # pragma: no cover - defensive
                log.debug("reg_open_key: CloseKey failed: %s", close_exc)
            finally:
                self._key = None


def reg_open_key(key: Any, sub_key: str, *, writable: bool = True) -> _RegKeyContext:
    """Open a registry key and return a context manager.

    On non-Windows, raises a RuntimeError with a clear message. Use
    :func:`require_windows` first if you want a graceful failure path.
    """
    wr = _ensure_winreg()
    if wr is None:
        raise RuntimeError("Registry access requires Windows")
    access = wr.KEY_WRITE if writable else wr.KEY_READ
    handle = wr.OpenKey(key, sub_key, 0, access)
    return _RegKeyContext(handle)


def reg_set_value(key_handle: Any, name: str, value: Any, *, type_: int | None = None) -> None:
    """SetValueEx with auto-inferred type (int -> REG_DWORD, else REG_SZ)."""
    wr = _ensure_winreg()
    if wr is None:
        raise RuntimeError("Registry access requires Windows")
    if type_ is None:
        type_ = wr.REG_DWORD if isinstance(value, int) else wr.REG_SZ
    wr.SetValueEx(key_handle, name, 0, type_, value)


def set_system_parameter(action: int, ui_param: int, param: Any, winini: int) -> tuple[bool, str]:
    """Wrap SystemParametersInfoW and check the return code.

    Returns (success, message). On non-Windows, returns a clear error.
    """
    if not is_windows:
        return False, "SystemParametersInfoW requires Windows"
    try:
        ok = ctypes.windll.user32.SystemParametersInfoW(action, ui_param, param, winini)
    except Exception as exc:
        return False, f"SystemParametersInfoW raised: {exc}"
    if not ok:
        err = ctypes.get_last_error()
        return False, f"SystemParametersInfoW failed (GetLastError={err})"
    return True, "OK"


def require_windows(feature: str) -> str | None:
    """Return an error message if not on Windows, else None.

    Usage::

        err = require_windows("Wallpaper apply")
        if err:
            return {"success": False, "message": err}
    """
    if is_windows:
        return None
    return f"{feature} requires Windows"
