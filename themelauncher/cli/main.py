"""
Theme Launcher SDK — CLI entry point.

Usage:
    python -m themelauncher.cli.main apply <theme_name>
    python -m themelauncher.cli.main list
    python -m themelauncher.cli.main snapshot capture
    python -m themelauncher.cli.main snapshot restore
    python -m themelauncher.cli.main generate <theme_dir>
    python -m themelauncher.cli.main recommend
    python -m themelauncher.cli.main circadian
    python -m themelauncher.cli.main check <theme_name>
    python -m themelauncher.cli.main audit
    python -m themelauncher.cli.main extract-7tsp <archive_path> <theme_name>
    python -m themelauncher.cli.main run-sfc
"""

import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from themelauncher.sdk import ThemeSDK


def main():
    if len(sys.argv) < 2:
        print("Theme Launcher SDK CLI")
        print("Usage:")
        print("  python -m themelauncher.cli.main list")
        print("  python -m themelauncher.cli.main apply <theme_name>")
        print("  python -m themelauncher.cli.main snapshot capture|restore|list")
        print("  python -m themelauncher.cli.main generate <theme_dir> [--name NAME]")
        print("  python -m themelauncher.cli.main recommend")
        print("  python -m themelauncher.cli.main circadian")
        print("  python -m themelauncher.cli.main check <theme_name>")
        return

    sdk = ThemeSDK()
    cmd = sys.argv[1]

    if cmd == "list":
        themes = sdk.get_themes()
        print(f"Discovered {len(themes)} theme(s):")
        for name in themes:
            print(f"  - {name}")

    elif cmd == "apply":
        if len(sys.argv) < 3:
            print("Usage: python -m themelauncher.cli.main apply <theme_name>")
            return
        theme_name = sys.argv[2]
        print(f"Applying theme: {theme_name}")
        result = sdk.apply_theme(theme_name)
        print(json.dumps(result, indent=2))

    elif cmd == "snapshot":
        if len(sys.argv) < 3:
            print("Usage: python -m themelauncher.cli.main snapshot capture|restore|list")
            return
        action = sys.argv[2]
        if action == "capture":
            snap_id = sdk.capture_snapshot()
            print(f"Snapshot captured: {snap_id}")
        elif action == "restore":
            snap_id = sys.argv[3] if len(sys.argv) > 3 else None
            result = sdk.restore_snapshot(snap_id)
            print(json.dumps(result, indent=2))
        elif action == "list":
            snaps = sdk.list_snapshots()
            for s in snaps:
                print(f"  {s['id']} - {s.get('datetime', 'unknown')}")

    elif cmd == "generate":
        if len(sys.argv) < 3:
            print("Usage: python -m themelauncher.cli.main generate <theme_dir>")
            return
        theme_dir = sys.argv[2]
        result = sdk.generate_manifest(theme_dir)
        print(json.dumps(result, indent=2))

    elif cmd == "recommend":
        recs = sdk.recommend()
        for r in recs:
            print(f"  {r['name']} - {r.get('reason', '')}")

    elif cmd == "circadian":
        result = sdk.circadian_suggest()
        print(json.dumps(result, indent=2))

    elif cmd == "check":
        if len(sys.argv) < 3:
            print("Usage: python -m themelauncher.cli.main check <theme_name>")
            return
        result = sdk.check_compatibility(sys.argv[2])
        print(json.dumps(result, indent=2))

    elif cmd == "audit":
        result = sdk.audit_themes()
        print(json.dumps(result, indent=2))

    elif cmd == "extract-7tsp":
        if len(sys.argv) < 4:
            print("Usage: python -m themelauncher.cli.main extract-7tsp <archive_path> <theme_name>")
            return
        archive_path = sys.argv[2]
        theme_name = sys.argv[3]
        result = sdk.extract_7tsp(archive_path, theme_name)
        print(json.dumps(result, indent=2))

    elif cmd == "run-sfc":
        from core.applier import Applier
        tm = sdk._load_theme_manager()
        if not tm:
            print("Theme manager not available")
            return
        applier = Applier(tm)
        result = applier.run_sfc_scan()
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()