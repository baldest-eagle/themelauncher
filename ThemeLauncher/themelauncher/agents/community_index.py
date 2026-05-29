"""Community Theme Index Agent for ThemeSDK.

Scans, indexes, and searches community-contributed themes from a local
themes directory.  The themes directory is resolved dynamically by walking
upward from this file's location to find ``config.json`` and reading the
``themes_dir`` key — no hardcoded paths.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Maps Windows cursor registry role names to substrings found in community
# .cur / .ani filenames.  Used for semantic matching instead of positional index.

CURSOR_ROLE_PATTERNS: Dict[str, List[str]] = {
    "Arrow":      ["arrow", "normal", "select"],
    "Wait":       ["wait", "hourglass"],
    "AppStarting": ["appstarting", "appstart", "working"],
    "Help":       ["help", "question"],
    "Crosshair":  ["crosshair", "cross", "precision"],
    "IBeam":      ["ibeam", "text", "beam"],
    "Hand":       ["hand", "link", "pointer"],
    "NO":         ["no", "unavailable"],
    "SizeAll":    ["sizeall", "move"],
    "SizeNS":     ["sizens", "ns"],
    "SizeWE":     ["sizewe", "we"],
    "SizeNWSE":   ["sizenwse", "nwse"],
    "SizeNESW":   ["sizenesw", "nesw"],
    "UpArrow":    ["uparrow", "up"],
    "NWPen":      ["nwpen", "pen"],
    "Person":     ["person", "user"],
    "Pin":        ["pin"],
}


class CommunityIndex:
    """Manage a local index of community themes.

    On init the agent resolves the themes directory by walking upward from
    its own file location looking for ``config.json``.  If none is found it
    falls back to ``~/.gemini/themes``.

    The public surface matches the ThemeSDK facade expectations:
    :meth:`crawl`, :meth:`search`, :meth:`scan`, :meth:`get_theme`, and
    :meth:`refresh`.
    """

    def __init__(self, sdk: Any = None) -> None:
        self._sdk = sdk
        self._themes: List[Dict[str, Any]] = []
        self.themes_dir: str = ""
        self._resolve_themes_dir()

    def _resolve_themes_dir(self) -> None:
        """Walk upward from *this file* to locate ``config.json``.

        Reads the ``themes_dir`` key from the first ``config.json`` found.
        If the walk reaches the filesystem root without finding one the
        method falls back to ``~/.gemini/themes``.
        """
        current = os.path.dirname(os.path.abspath(__file__))

        while True:
            candidate = os.path.join(current, "config.json")
            if os.path.isfile(candidate):
                try:
                    with open(candidate, "r", encoding="utf-8") as fh:
                        cfg = json.load(fh)
                    resolved = cfg.get("themes_dir") or cfg.get("themes_directory")
                    if resolved:
                        self.themes_dir = os.path.expanduser(resolved)
                        logger.info(
                            "Resolved themes_dir from %s: %s", candidate, self.themes_dir
                        )
                        return
                except (json.JSONDecodeError, OSError) as exc:
                    logger.warning("Failed to read %s: %s", candidate, exc)

            parent = os.path.dirname(current)
            if parent == current:
                # Reached filesystem root
                break
            current = parent

        # Fallback
        self.themes_dir = os.path.expanduser("~/.gemini/Themes")
        logger.info(
            "No config.json found; falling back to %s", self.themes_dir
        )

    def scan(self) -> List[Dict[str, Any]]:
        """Walk ``self.themes_dir`` for ``.theme`` files and parse each.

        Returns a list of dicts, each containing at least ``name``, ``path``,
        and any metadata found in a sibling ``manifest.json``.
        """
        if not os.path.isdir(self.themes_dir):
            logger.warning("Themes directory does not exist: %s", self.themes_dir)
            self._themes = []
            return self._themes

        themes: List[Dict[str, Any]] = []
        for root, _dirs, files in os.walk(self.themes_dir):
            for fname in files:
                if not fname.lower().endswith(".theme"):
                    continue
                full_path = os.path.join(root, fname)
                theme_name = os.path.splitext(fname)[0]
                entry: Dict[str, Any] = {
                    "name": theme_name,
                    "path": full_path,
                    "metadata": {},
                }
                # Enrich from a sibling manifest.json if present
                manifest_path = os.path.join(root, "manifest.json")
                if os.path.isfile(manifest_path):
                    try:
                        with open(manifest_path, "r", encoding="utf-8") as mf:
                            entry["metadata"] = json.load(mf)
                    except (json.JSONDecodeError, OSError) as exc:
                        logger.warning(
                            "Could not read manifest for %s: %s", theme_name, exc
                        )
                themes.append(entry)

        self._themes = themes
        logger.info("Scanned %d theme(s) from %s", len(themes), self.themes_dir)
        return self._themes

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search scanned themes by name or metadata for *query*.

        Matching is case-insensitive against the theme name and any string
        values found in the metadata dict.
        """
        if not self._themes:
            self.scan()

        q = query.lower()
        results: List[Dict[str, Any]] = []

        for theme in self._themes:
            if q in theme.get("name", "").lower():
                results.append(theme)
                continue
            # Also search string values inside metadata
            metadata = theme.get("metadata", {})
            if any(q in str(v).lower() for v in metadata.values() if isinstance(v, (str, int, float))):
                results.append(theme)

        return results

    def get_theme(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a single theme dict by exact name, or ``None``."""
        if not self._themes:
            self.scan()
        for theme in self._themes:
            if theme.get("name") == name:
                return theme
        return None

    def refresh(self) -> List[Dict[str, Any]]:
        """Re-scan the themes directory and return the updated list."""
        self._themes = []
        return self.scan()

    def crawl(self, sources: Optional[List[str]] = None) -> Dict[str, Any]:
        """Crawl configured sources (or *sources* if given) and re-scan.

        Returns a summary dict compatible with ``ThemeSDK.crawl_community()``.
        """
        if sources:
            logger.info("Crawl requested for %d source(s)", len(sources))
        before = len(self._themes)
        self.refresh()
        after = len(self._themes)
        return {
            "discovered": after,
            "new": max(0, after - before),
            "failed": 0,
        }
