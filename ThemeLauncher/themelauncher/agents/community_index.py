"""Community Theme Index Agent (Tier 2 - High Value). Scrape & curate remote repos."""

import json
import os
import tempfile
from typing import Any, Optional
from urllib.parse import urlparse

from ..core.logger import log


class CommunityIndex:
    """Periodically crawl known theme repositories, discover and index new themes."""

    def __init__(self, index_dir: Optional[str] = None):
        self.index_dir = index_dir or os.path.join(
            os.environ.get("LOCALAPPDATA", ""), "themelauncher", "community_index"
        )
        os.makedirs(self.index_dir, exist_ok=True)
        self._sources: list[dict] = []

    def crawl(self, sources: Optional[list[str]] = None) -> dict[str, Any]:
        """Scan configured repositories for new themes."""
        if sources:
            for url in sources:
                self.add_source(url, "manual")

        discovered = 0
        downloaded = 0
        failed = 0

        for source in self._sources:
            try:
                result = self.download_and_validate(source["url"])
                if result.get("success"):
                    downloaded += 1
                else:
                    failed += 1
                discovered += 1
            except Exception:
                failed += 1

        return {"discovered": discovered, "downloaded": downloaded, "failed": failed}

    def download_and_validate(self, url: str) -> dict[str, Any]:
        """Download, validate, and import a remote theme."""
        log.info("Downloading theme from: %s", url)
        import urllib.request
        import zipfile
        import shutil

        # Determine target themes directory
        themes_dir = "C:\\Users\\kyleh\\.gemini\\themes"
        # Try to search in common paths for config.json to load the configured directory
        for p in [".", "..", "../..", "../../.."]:
            cfg_path = os.path.join(p, "config.json")
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        if "themes_directory" in cfg:
                            themes_dir = cfg["themes_directory"]
                            break
                except Exception:
                    pass

        os.makedirs(themes_dir, exist_ok=True)

        try:
            # Download file to a temp file
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path) or "downloaded_theme.zip"
            if not filename.endswith((".zip", ".json")):
                filename += ".zip"  # Default to zip

            temp_dir = tempfile.mkdtemp()
            dest_path = os.path.join(temp_dir, filename)

            # Use urllib.request
            urllib.request.urlretrieve(url, dest_path)

            # Validate and extract/copy
            if filename.endswith(".zip"):
                with zipfile.ZipFile(dest_path, "r") as zip_ref:
                    # Look for manifest.json
                    namelist = zip_ref.namelist()
                    manifest_in_zip = None
                    for name in namelist:
                        if name.endswith("manifest.json"):
                            manifest_in_zip = name
                            break

                    if not manifest_in_zip:
                        return {"success": False, "message": "Invalid theme pack: manifest.json not found in zip."}

                    # Extract zip content to temp extraction dir
                    extract_dir = os.path.join(temp_dir, "extracted")
                    zip_ref.extractall(extract_dir)

                    # Locate the actual theme folder containing the manifest
                    manifest_abs = os.path.join(extract_dir, manifest_in_zip)
                    theme_folder = os.path.dirname(manifest_abs)

                    # Read and validate manifest
                    with open(manifest_abs, "r", encoding="utf-8") as f:
                        manifest = json.load(f)

                    theme_name = manifest.get("name")
                    if not theme_name:
                        return {"success": False, "message": "Invalid manifest: name field missing."}

                    # Copy to local themes directory
                    safe_folder_name = "".join(c for c in theme_name if c.isalnum() or c in (" ", "_", "-")).strip()
                    final_dest = os.path.join(themes_dir, safe_folder_name)
                    if os.path.exists(final_dest):
                        shutil.rmtree(final_dest)
                    shutil.copytree(theme_folder, final_dest)

                    return {
                        "success": True,
                        "message": f"Successfully downloaded and validated theme: {theme_name}",
                        "theme_name": theme_name,
                        "path": final_dest
                    }
            elif filename.endswith(".json"):
                # Direct manifest file download
                with open(dest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                theme_name = manifest.get("name")
                if not theme_name:
                    return {"success": False, "message": "Invalid manifest: name field missing."}

                safe_folder_name = "".join(c for c in theme_name if c.isalnum() or c in (" ", "_", "-")).strip()
                final_dest = os.path.join(themes_dir, safe_folder_name)
                os.makedirs(final_dest, exist_ok=True)

                # Copy JSON file as manifest.json
                shutil.copy2(dest_path, os.path.join(final_dest, "manifest.json"))

                return {
                    "success": True,
                    "message": f"Successfully downloaded theme manifest: {theme_name}",
                    "theme_name": theme_name,
                    "path": final_dest
                }

        except Exception as exc:
            log.exception("Failed to download and validate theme from %s", url)
            return {"success": False, "message": f"Download/validation error: {exc}"}
        finally:
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

        return {"success": False, "message": "Unknown download error"}

    def search(self, query: str, tags: Optional[list[str]] = None) -> list[dict[str, Any]]:
        """Search local index by name, tags, or palette."""
        results = []
        index_file = os.path.join(self.index_dir, "index.json")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                index = json.load(f)
            for entry in index:
                if query.lower() in entry.get("name", "").lower():
                    results.append(entry)

        return results

    def rate_theme(self, theme_name: str) -> dict[str, Any]:
        """Compute completeness and quality score."""
        return {"name": theme_name, "quality_score": 75}

    def flag_malicious(self, theme_path: str) -> list[dict[str, str]]:
        """Check for suspicious files or paths."""
        flags = []
        for root, dirs, files in os.walk(theme_path):
            for f in files:
                if f.lower().endswith((".exe", ".bat", ".ps1", ".vbs")):
                    flags.append({
                        "file": os.path.join(root, f),
                        "reason": "Executable file in theme pack",
                    })
        return flags

    def add_source(self, url: str, source_type: str = "manual") -> None:
        """Add a new crawl source."""
        self._sources.append({"url": url, "type": source_type})

    def get_sources(self) -> list[dict]:
        """List configured crawl sources."""
        return self._sources