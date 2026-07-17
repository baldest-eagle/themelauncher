"""
7TSP Extractor Agent (Tier 2 - High Value).

Extracts and converts legacy 7TSP icon packs to Windhawk format.
Follows the bot-builder workflow:
1. Extraction: Unpack archive to /assets/temp_extracted/
2. Resource Re-mapping: Convert .res files to .dll
3. Manifest Generation: Create theme.ini with binary mappings
4. Directory Staging: Move to /themes/[ThemeName]/Icons/
5. Intelligent icon mapping for standalone .ico files to Windhawk Resource Redirect
"""

import os
import shutil
import zipfile
from typing import Any, Optional

from ..core.logger import log


def _is_pe_dll(path: str) -> bool:
    """Return True if ``path`` starts with the PE ``MZ`` magic.

    7TSP packs sometimes ship non-PE ``.res`` files (HTML/XML/resource
    scripts, asset lists, even text files) that just happen to have a ``.res``
    extension. Renaming those to ``.dll`` produces broken files that Windows
    refuses to load — so we validate the magic before renaming.
    """
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"MZ"
    except OSError:
        return False


def _unpack_archive(archive_path: str, extract_to: str) -> None:
    """Unpack ``archive_path`` into ``extract_to``.

    Dispatches on extension:
      * ``.7z``  → py7zr (raises a clear error if not installed)
      * ``.exe`` → try py7zr (SFX archives), fall back to shutil
      * anything else (``.zip``, ``.tar.*``) → shutil.unpack_archive
    """
    ext = os.path.splitext(archive_path)[1].lower()
    if ext == ".7z" or ext == ".exe":
        try:
            import py7zr
        except ImportError as exc:
            raise RuntimeError(
                f"Extracting {ext} archives requires the optional 'py7zr' package. "
                f"Install it with: pip install py7zr"
            ) from exc
        with py7zr.SevenZipFile(archive_path, mode="r") as z:
            z.extractall(path=extract_to)
        return
    # Standard formats (zip / tar / gztar / bztar / xztar)
    shutil.unpack_archive(archive_path, extract_to)


class SevenTSPExtractor:
    """Extract and convert 7TSP icon packs for Windhawk."""

    def __init__(self, assets_dir: Optional[str] = None):
        if assets_dir is None:
            self.assets_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "assets"
            )
        else:
            self.assets_dir = assets_dir
        self.temp_dir = os.path.join(self.assets_dir, "temp_extracted")

    def extract(self, archive_path: str, theme_name: Optional[str] = None) -> dict[str, Any]:
        """Phase 1: Extract 7TSP archive to temp workspace."""
        if not os.path.exists(archive_path):
            return {"success": False, "message": f"Archive not found: {archive_path}"}

        os.makedirs(self.temp_dir, exist_ok=True)

        name = theme_name or os.path.splitext(os.path.basename(archive_path))[0]
        extract_to = os.path.join(self.temp_dir, name)
        os.makedirs(extract_to, exist_ok=True)

        try:
            _unpack_archive(archive_path, extract_to)
            log.info("Extracted 7TSP archive to: %s", extract_to)
            return {
                "success": True,
                "extract_path": extract_to,
                "files": self._list_extracted(extract_to),
            }
        except Exception as exc:
            return {"success": False, "message": f"Extraction failed: {exc}"}

    def remap_resources(self, source_dir: str) -> dict[str, Any]:
        """Phase 2: Convert .res files to .dll format for Windhawk.

        Only renames files that actually start with the PE ``MZ`` magic — a
        non-PE ``.res`` (asset list, manifest XML, text) is left in place and
        logged, so we don't produce broken ``.dll`` files Windows can't load.
        """
        remapped = []
        skipped = []

        for root, dirs, files in os.walk(source_dir):
            for filename in files:
                if filename.lower().endswith(".res"):
                    old_path = os.path.join(root, filename)
                    if not _is_pe_dll(old_path):
                        skipped.append(f"{filename}: not a PE image (no MZ magic)")
                        log.info("Skipping non-PE .res file: %s", old_path)
                        continue
                    new_name = filename.lower()[:-4] + ".dll"
                    new_path = os.path.join(root, new_name)
                    try:
                        shutil.copy2(old_path, new_path)
                        os.remove(old_path)
                        remapped.append(f"{filename} -> {new_name}")
                        log.info("Remapped: %s", old_path)
                    except Exception as exc:
                        skipped.append(f"{filename}: {exc}")
                        log.warning("Failed to remap %s: %s", old_path, exc)

        return {
            "success": True,
            "remapped": remapped,
            "skipped": skipped,
        }

    def process_ico_files(self, source_dir: str, theme_name: str, themes_dir: str) -> dict[str, Any]:
        """Process standalone .ico files for Windhawk Resource Redirect.

        Intelligently maps icon filenames to system DLL/resource indices
        and deploys them to the correct Windhawk resources directory.
        """
        icon_files = []
        for filename in os.listdir(source_dir):
            if filename.lower().endswith(".ico"):
                icon_files.append(filename)

        if not icon_files:
            return {"success": False, "message": "No .ico files found to process"}

        # Use intelligent mapping
        from .converter import IconPackConverter
        converter = IconPackConverter()
        mapping = converter.infer_mapping(icon_files)

        if not mapping["mapped"]:
            return {"success": False, "message": "No icons could be mapped to system resources"}

        # Create Windhawk Resources directory
        wh_res_dir = os.path.join(themes_dir, theme_name, "Windhawk Resources")
        os.makedirs(wh_res_dir, exist_ok=True)

        deployed = []
        for entry in mapping["mapped"]:
            src = os.path.join(source_dir, entry["file"])
            if os.path.exists(src):
                dest_name = f"{entry['dll'].replace('.dll', '')}_{entry['index']}.ico"
                dest = os.path.join(wh_res_dir, dest_name)
                try:
                    shutil.copy2(src, dest)
                    deployed.append(dest_name)
                except Exception as exc:
                    log.warning("Failed to deploy %s: %s", entry["file"], exc)

        # Also copy any unmapped icons as-is
        for fname in mapping.get("unmapped", []):
            src = os.path.join(source_dir, fname)
            dest = os.path.join(wh_res_dir, fname)
            if os.path.exists(src):
                try:
                    shutil.copy2(src, dest)
                    deployed.append(fname)
                except Exception as exc:
                    log.warning("Failed to copy unmapped %s: %s", fname, exc)

        return {
            "success": True,
            "deployed": deployed,
            "mapped": len(mapping["mapped"]),
            "unmapped": len(mapping["unmapped"]),
            "windhawk_dir": wh_res_dir,
        }

    def generate_theme_ini(self, source_dir: str, output_path: str) -> dict[str, Any]:
        """Phase 3: Generate theme.ini with system binary mappings.

        Emits valid ``key=value`` INI lines under ``[Icons]`` (was previously
        writing bare DLL filenames, which is not valid INI and confused
        parsers). Walks ``source_dir`` recursively so nested DLL folders work.
        """
        dll_files = []
        for root, dirs, files in os.walk(source_dir):
            for filename in files:
                if filename.lower().endswith(".dll"):
                    rel = os.path.relpath(os.path.join(root, filename), source_dir)
                    dll_files.append(rel)

        lines = [
            "[General]",
            f"Name={os.path.basename(source_dir)}",
            "Author=ThemeLauncher 7TSP Extractor",
            "Description=Converted from 7TSP to Windhawk format",
            "",
            "[Icons]",
        ]

        # Emit a ``key=value`` line per DLL: the DLL filename (relative path)
        # becomes the key, and the value is the path inside the theme folder.
        for dll in dll_files:
            # Sanitize to an INI-safe key (no spaces, no backslashes).
            key = os.path.basename(dll).replace(".dll", "")
            lines.append(f"{key}={dll}")

        # Map standard Windows system DLLs (kept for backwards compat).
        lines.append("")
        lines.append("[SystemMappings]")
        system_mappings = [
            "imageres=%SystemRoot%\\\\System32\\\\imageres.dll",
            "shell32=%SystemRoot%\\\\System32\\\\shell32.dll",
            "explorer=%SystemRoot%\\\\explorer.exe",
        ]
        for mapping in system_mappings:
            lines.append(mapping)

        ini_content = "\n".join(lines) + "\n"

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(ini_content)
            return {
                "success": True,
                "ini_path": output_path,
                "dll_files": dll_files,
            }
        except Exception as exc:
            return {"success": False, "message": f"Failed to write ini: {exc}"}

    def stage_icons(self, source_dir: str, theme_name: str, themes_dir: str) -> dict[str, Any]:
        """Phase 4: Move assets to /themes/[ThemeName]/Icons/ and clean temp.

        Walks ``source_dir`` recursively (7TSP packs commonly nest DLLs in
        subfolders). Collisions (two files with the same basename in different
        subfolders) are disambiguated with a numeric suffix.
        """
        theme_icon_dir = os.path.join(themes_dir, theme_name, "Icons")
        os.makedirs(theme_icon_dir, exist_ok=True)

        staged = []
        seen_basenames: dict[str, int] = {}
        for root, dirs, files in os.walk(source_dir):
            for filename in files:
                if not filename.lower().endswith(".dll"):
                    continue
                src = os.path.join(root, filename)
                # Handle same-name collisions with a numeric suffix.
                base = filename
                if base in seen_basenames:
                    seen_basenames[base] += 1
                    stem, ext = os.path.splitext(base)
                    dst_name = f"{stem}_{seen_basenames[base]}{ext}"
                else:
                    seen_basenames[base] = 0
                    dst_name = base
                dst = os.path.join(theme_icon_dir, dst_name)
                try:
                    shutil.copy2(src, dst)
                    staged.append(dst_name)
                except Exception as exc:
                    log.warning("Failed to stage %s: %s", filename, exc)

        # Clean temp directory
        temp_theme = os.path.join(self.temp_dir, theme_name)
        if os.path.exists(temp_theme):
            shutil.rmtree(temp_theme, ignore_errors=True)

        return {
            "success": True,
            "staged": staged,
            "icon_dir": theme_icon_dir,
        }

    def full_pipeline(self, archive_path: str, theme_name: str, themes_dir: str) -> dict[str, Any]:
        """Run the complete 7TSP extraction pipeline.

        Handles both .res/.dll files AND standalone .ico files for Windhawk Resource Redirect.
        """
        # Phase 1: Extract
        extract_result = self.extract(archive_path, theme_name)
        if not extract_result["success"]:
            return extract_result

        extract_path = extract_result["extract_path"]

        results = {
            "success": True,
            "theme": theme_name,
            "extracted_to": extract_path,
        }

        # Phase 2: Process .ico files for Windhawk Resource Redirect
        ico_result = self.process_ico_files(extract_path, theme_name, themes_dir)
        if ico_result["success"]:
            results["windhawk_icons"] = {
                "deployed": len(ico_result["deployed"]),
                "mapped": ico_result["mapped"],
                "unmapped": ico_result["unmapped"],
                "windhawk_dir": ico_result["windhawk_dir"],
            }

        # Phase 3: Remap .res to .dll
        remap_result = self.remap_resources(extract_path)
        results["remapped"] = len(remap_result["remapped"])

        # Phase 4: Generate theme.ini
        ini_path = os.path.join(extract_path, "theme.ini")
        ini_result = self.generate_theme_ini(extract_path, ini_path)
        if ini_result["success"]:
            results["ini_path"] = ini_path
            results["dll_files"] = ini_result["dll_files"]

        # Phase 5: Stage .dll files to Icons directory
        stage_result = self.stage_icons(extract_path, theme_name, themes_dir)
        if stage_result["success"]:
            results["staged_dlls"] = len(stage_result["staged"])
            results["icon_dir"] = stage_result["icon_dir"]

        return results

    def _list_extracted(self, directory: str) -> list[str]:
        """List all files in extracted directory."""
        files = []
        for root, dirs, filenames in os.walk(directory):
            for filename in filenames:
                files.append(os.path.relpath(os.path.join(root, filename), directory))
        return files