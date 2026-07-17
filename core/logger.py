"""
Centralised logging for the Theme Launcher.

Every module does ``from core.logger import log`` instead of calling print().
Logs go to both the console and a rotating file next to the executable.

Robustness: logger init never crashes the app. If the log directory isn't
writable (e.g., running from ``C:\\Program Files\\``) or the file handler
can't be created (locked by another instance), we fall back to a temp dir
or console-only logging.
"""

import logging
import os
import tempfile
from logging.handlers import RotatingFileHandler

_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "theme_launcher.log")
_MAX_BYTES = 2 * 1024 * 1024
_BACKUP_COUNT = 3

_logger: logging.Logger | None = None


def _resolve_log_dir() -> str:
    """Return a writable log directory. Falls back to tempfile.gettempdir()."""
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        # Touch-test writability
        test_file = os.path.join(_LOG_DIR, ".write_test")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(test_file)
        return _LOG_DIR
    except OSError:
        fallback = os.path.join(tempfile.gettempdir(), "themelauncher_logs")
        try:
            os.makedirs(fallback, exist_ok=True)
        except OSError:
            # Last resort: don't write logs at all
            return ""
        return fallback


def _init() -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("ThemeLauncher")
    logger.setLevel(logging.DEBUG)

    # Dedup guard — don't double-add handlers if _init is called twice
    if not logger.handlers:
        # Console handler — INFO and above
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(ch)

        # File handler — DEBUG and above, rotating. Guard against OSError /
        # PermissionError so a locked or read-only log path doesn't crash
        # the whole app.
        try:
            log_dir = _resolve_log_dir()
            if log_dir:
                log_file = os.path.join(log_dir, "theme_launcher.log")
                fh = RotatingFileHandler(
                    log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
                )
                fh.setLevel(logging.DEBUG)
                fh.setFormatter(
                    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
                )
                logger.addHandler(fh)
            else:
                logging.getLogger().warning(
                    "ThemeLauncher: no writable log directory — console-only logging"
                )
        except (OSError, PermissionError) as exc:
            logging.getLogger().warning(
                "ThemeLauncher: file handler unavailable (%s) — console-only logging", exc
            )

    _logger = logger
    return _logger


# Public alias — lazy-initialised on first import.
# Guard the init call so a buggy logger config never crashes app startup.
try:
    log = _init()
except Exception as exc:  # pragma: no cover - defensive
    logging.getLogger().warning("ThemeLauncher: logger init failed (%s); using root", exc)
    log = logging.getLogger("ThemeLauncher")
