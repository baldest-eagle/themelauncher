"""
SDK Logger — lightweight logging utility for the themelauncher SDK.
Writes to both console and a log file in the user's local app data.
"""

import logging
import os
import sys
import threading

LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ".themelauncher"), "logs")

# Singleton pattern: configure once, use everywhere.
_configured = False
_init_lock = threading.Lock()


def _ensure_configured():
    """Configure the SDK logger.

    Robust against a non-writable LOG_DIR (e.g. running from Program Files, or
    a locked log file from another instance): on any failure we fall back to a
    console-only logger and print a diagnostic to stderr. A non-writable log
    directory must NEVER crash SDK import — too many modules do
    ``from themelauncher.core.logger import log`` at import time.
    """
    global _configured
    if _configured:
        return

    with _init_lock:
        if _configured:
            return

        logger = logging.getLogger("themelauncher")
        logger.setLevel(logging.DEBUG)

        # Only add handlers once — concurrent imports or repeated calls must
        # not stack duplicate handlers on the same logger.
        if not logger.handlers:
            log_file = os.path.join(LOG_DIR, "themelauncher.log")
            try:
                os.makedirs(LOG_DIR, exist_ok=True)
                fh = logging.FileHandler(log_file, encoding="utf-8")
                fh.setLevel(logging.DEBUG)
                fh.setFormatter(logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                ))
                logger.addHandler(fh)
                logger.info("SDK logger initialized at %s", log_file)
            except Exception as exc:  # pragma: no cover - environment dependent
                # Fall back to console-only logging. Never raise.
                print(f"[themelauncher] WARNING: could not initialize file logger "
                      f"at {LOG_DIR!r}: {exc}", file=sys.stderr)

            try:
                ch = logging.StreamHandler(sys.stdout)
                ch.setLevel(logging.INFO)
                ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
                logger.addHandler(ch)
            except Exception as exc:  # pragma: no cover - defensive
                print(f"[themelauncher] WARNING: could not initialize console "
                      f"logger: {exc}", file=sys.stderr)

        _configured = True


try:
    _ensure_configured()
except Exception as _exc:  # pragma: no cover - last-resort guard
    print(f"[themelauncher] WARNING: logger init failed: {_exc}", file=sys.stderr)

log = logging.getLogger("themelauncher")
