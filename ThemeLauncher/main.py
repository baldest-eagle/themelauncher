#!/usr/bin/env python3
"""
Theme Launcher — main entry point.

Usage:
    python main.py              # Normal launch
    python main.py --admin      # Launch with admin elevation prompt
"""

import sys
import os
import ctypes

# Ensure the project root is on sys.path so `core.*` and `ui.*` resolve
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def is_admin() -> bool:
    """Check if the current process is running with administrator privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except AttributeError:
        return False


def request_admin():
    """Re-launch the script with admin elevation via UAC prompt."""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable,
        " ".join([f'"{arg}"' for arg in sys.argv]),
        None, 1,
    )


def main():
    from core.logger import log
    from themelauncher.sdk import ThemeSDK
    from ui.app import App

    import customtkinter as ctk

    log.info("Theme Launcher starting...")

    # Check for --admin flag
    if "--admin" in sys.argv and not is_admin():
        log.info("Requesting admin elevation...")
        request_admin()
        sys.exit(0)

    if is_admin():
        log.info("Running with administrator privileges")
    else:
        log.warning(
            "Not running as administrator. "
            "Font installation and some registry operations will fail. "
            "Re-launch with --admin flag for full functionality."
        )

    # Load configuration
    config_path = os.path.join(PROJECT_ROOT, "config.json")
    if not os.path.exists(config_path):
        log.error("config.json not found at %s", config_path)
        print(f"ERROR: config.json not found at {config_path}")
        print("Create a config.json with at least:")
        print('  { "themes_directory": "C:\\\\path\\\\to\\\\themes" }')
        sys.exit(1)

    try:
        # Initialize the unified ThemeSDK
        sdk = ThemeSDK(config_path=config_path)
        manager = sdk.theme_manager
    except Exception as exc:
        log.exception("Failed to initialize ThemeSDK facade")
        sys.exit(1)

    # Discover themes once
    themes = manager.discover_themes()
    log.info("Discovered %d theme(s)", len(themes))

    # Set dark mode for customtkinter
    ctk.set_appearance_mode("dark")

    # Start Windows Update Resilience Monitor in the background
    try:
        sdk.watch_for_updates()
        log.info("Windows Update Resilience Monitor active")
    except Exception as exc:
        log.warning("Could not start update watch: %s", exc)

    # Start Scheduled Theme Switcher in the background
    try:
        sdk.start_scheduler()
        log.info("Scheduled Theme Switcher active")
    except Exception as exc:
        log.warning("Could not start theme scheduler: %s", exc)

    # Launch the app with the SDK facade
    app = App(sdk)

    # Set the window icon if available
    icon_path = os.path.join(PROJECT_ROOT, "icon.ico")
    if os.path.exists(icon_path):
        app.iconbitmap(icon_path)

    log.info("Theme Launcher UI ready")
    app.mainloop()

    # Stop background agents gracefully on exit
    try:
        sdk.stop_scheduler()
        log.info("Theme scheduler stopped")
    except Exception:
        pass

    log.info("Theme Launcher closed")


if __name__ == "__main__":
    main()
