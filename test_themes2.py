#!/usr/bin/env python3
import sys
import os

# Add the core directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'core'))

from core.theme_manager import ThemeManager
import logging

# Enable debug logging
logging.basicConfig(level=logging.WARNING)

def test_theme_loading():
    print("Testing theme loading...")
    try:
        # Create a theme manager with the default config
        tm = ThemeManager()
        
        # Discover themes
        themes = tm.discover_themes()
        
        print(f"Successfully loaded {len(themes)} themes:")
        for name, theme_data in themes.items():
            print(f"  - {name}")
            
        # Try to get the active theme
        active = tm.active_theme
        if active:
            print(f"\nActive theme: {active}")
            active_theme_data = tm.get_theme(active)
            if active_theme_data:
                manifest = active_theme_data["manifest"]
                print(f"  Version: {manifest.get('version')}")
                print(f"  Author: {manifest.get('author')}")
                components = manifest.get('components', {})
                print(f"  Components: {', '.join(components.keys())}")
            else:
                print(f"  ERROR: Could not get theme data for {active}")
        else:
            print("\nNo active theme set")
            
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_theme_loading()
    sys.exit(0 if success else 1)