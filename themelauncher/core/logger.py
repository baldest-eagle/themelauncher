"""
SDK Logger — lightweight logging utility for the themelauncher SDK.
Writes to both console and a log file in the user's local app data.
"""

import logging
import os
import sys

LOG_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ".themelauncher"), "logs")

# Singleton pattern: configure once, use everywhere
_configured = False


def _ensure_configured():
    global _configured
    if _configured:
        return

    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, "themelauncher.log")

    logger = logging.getLogger("themelauncher")
    logger.setLevel(logging.DEBUG)

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ch)

    _configured = True
    logger.info("SDK logger initialized at %s", log_file)


_ensure_configured()
log = logging.getLogger("themelauncher")