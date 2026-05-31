"""
One-shot script to copy theme files into the structured launcher format
and write manifest.json for each theme.

Key discovery from file inspection:
  - .theme files always live at Resources_Themes_Folder root (NOT in variant/Shell subfolders)
  - .msstyles live in each variant's root folder
  - DRK 25 msstyles use: DRK3=MAC, DRK2=SQR, DRK=WIN  (plus 25b variants)
"""

import json
import os
import shutil
from pathlib import Path

THEMES_DIR = Path(r"C:\Users\kyleh\.gemini\Themes")


def cp(src: Path, dst: Path):
    if not src.exists():
        print(f"  [MISSING] {src}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def cp_tree(src: Path, dst: Path):
    if not src.exists():
        print(f"  [MISSING DIR] {src}")
        return
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def write_manifest(target: Path, data: dict):
    target.mkdir(parents=True, exist_ok=True)
    (target / "manifest.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"  [manifest] {target / 'manifest.json'}")


# ============================================================================
# THEME 1 — SynthWave '84
# ============================================================================
print("\n=== SynthWave '84 ===")

SW_SRC = Path(
    r"C:\Users\kyleh\Documents\Projects\2H24Themes\Themes\SynthWave '84 for Windows 11 - (by niivu)"
)
SW_RTF = SW_SRC / "Resources_Themes_Folder"
SW_VAR = SW_RTF / "SynthWave '84"
SW_DST = THEMES_DIR / "SynthWave 84"

cp(SW_SRC / "SynthWave '84 PREVIEW.png", SW_DST / "preview.png")

sw_msstyles = [
    "SynthWave '84 dark - luv NA.msstyles",
    "SynthWave '84 dark - luv.msstyles",
    "SynthWave '84 dark - mac GLOSS NA.msstyles",
    "SynthWave '84 dark - mac GLOSS.msstyles",
    "SynthWave '84 dark - mac NA.msstyles",
    "SynthWave '84 dark - mac.msstyles",
    "SynthWave '84 dark - nude NA.msstyles",
    "SynthWave '84 dark - nude.msstyles",
    "SynthWave '84 night - luv NA.msstyles",
    "SynthWave '84 night - luv.msstyles",
    "SynthWave '84 night - mac GLOSS NA.msstyles",
    "SynthWave '84 night - mac GLOSS.msstyles",
    "SynthWave '84 night - mac NA.msstyles",
    "SynthWave '84 night - mac.msstyles",
    "SynthWave '84 night - nude NA.msstyles",
    "SynthWave '84 night - nude.msstyles",
]
for f in sw_msstyles:
    cp(SW_VAR / f, SW_DST / "msstyles" / f)

sw_themes = [
    "SynthWave '84 dark - luv NA.theme",
    "SynthWave '84 dark - luv.theme",
    "SynthWave '84 dark - mac gloss NA.theme",
    "SynthWave '84 dark - mac gloss.theme",
    "SynthWave '84 dark - mac NA.theme",
    "SynthWave '84 dark - mac.theme",
    "SynthWave '84 dark - nude NA.theme",
    "SynthWave '84 dark - nude.theme",
    "SynthWave '84 night - luv NA.theme",
    "SynthWave '84 night - luv.theme",
    "SynthWave '84 night - mac gloss NA.theme",
    "SynthWave '84 night - mac gloss.theme",
    "SynthWave '84 night - mac NA.theme",
    "SynthWave '84 night - mac.theme",
    "SynthWave '84 night - nude NA.theme",
    "SynthWave '84 night - nude.theme",
]
for f in sw_themes:
    cp(SW_RTF / f, SW_DST / "themes" / f)

sw_wallpapers = [
    "UNSPLASH-NIIVU (1).jpg",
    "UNSPLASH-NIIVU (2).jpg",
    "UNSPLASH-NIIVU (3).jpg",
    "UNSPLASH-NIIVU (4).jpg",
    "UNSPLASH-NIIVU (5).jpg",
    "UNSPLASH-NIIVU (6).jpg",
    "UNSPLASH-NIIVU (7).jpg",
    "UNSPLASH-NIIVU (8).png",
    "wallpaperflare.com.png",
]
for f in sw_wallpapers:
    cp(SW_VAR / "Wallpapers" / f, SW_DST / "wallpapers" / f)

for f in (SW_VAR / "Previews").glob("*"):
    cp(f, SW_DST / "previews" / f.name)

cp_tree(SW_VAR / "Cursors", SW_DST / "cursors")

sw_mss_variants = [
    {"name": "Dark - Luv", "file": "msstyles/SynthWave '84 dark - luv.msstyles",
     "preview": "previews/SynthWave '84 dark - luv.png"},
    {"name": "Dark - Mac", "file": "msstyles/SynthWave '84 dark - mac.msstyles",
     "preview": "previews/SynthWave '84 dark - mac.png"},
    {"name": "Dark - Mac Gloss", "file": "msstyles/SynthWave '84 dark - mac GLOSS.msstyles",
     "preview": "previews/SynthWave '84 dark - mac gloss.png"},
    {"name": "Dark - Nude", "file": "msstyles/SynthWave '84 dark - nude.msstyles",
     "preview": "previews/SynthWave '84 dark - nude.png"},
    {"name": "Night - Luv", "file": "msstyles/SynthWave '84 night - luv.msstyles",
     "preview": "previews/SynthWave '84 night - luv.png"},
    {"name": "Night - Mac", "file": "msstyles/SynthWave '84 night - mac.msstyles",
     "preview": "previews/SynthWave '84 night - mac.png"},
    {"name": "Night - Mac Gloss", "file": "msstyles/SynthWave '84 night - mac GLOSS.msstyles",
     "preview": "previews/SynthWave '84 night - mac gloss.png"},
    {"name": "Night - Nude", "file": "msstyles/SynthWave '84 night - nude.msstyles",
     "preview": "previews/SynthWave '84 night - nude.png"},
]
sw_theme_variants = [
    {"name": "Dark - Luv", "file": "themes/SynthWave '84 dark - luv.theme"},
    {"name": "Dark - Mac", "file": "themes/SynthWave '84 dark - mac.theme"},
    {"name": "Dark - Mac Gloss", "file": "themes/SynthWave '84 dark - mac gloss.theme"},
    {"name": "Dark - Nude", "file": "themes/SynthWave '84 dark - nude.theme"},
    {"name": "Night - Luv", "file": "themes/SynthWave '84 night - luv.theme"},
    {"name": "Night - Mac", "file": "themes/SynthWave '84 night - mac.theme"},
    {"name": "Night - Mac Gloss", "file": "themes/SynthWave '84 night - mac gloss.theme"},
    {"name": "Night - Nude", "file": "themes/SynthWave '84 night - nude.theme"},
]
sw_wall_variants = [
    {"name": f"Wallpaper {i + 1}", "file": f"wallpapers/{f}"}
    for i, f in enumerate(sw_wallpapers)
]

sw_manifest = {
    "name": "SynthWave '84",
    "version": "1.0.0",
    "description": "A retro synthwave-inspired dark theme for Windows 11 with neon accents by niivu.",
    "author": "niivu",
    "preview": "preview.png",
    "palette": {
        "background": "#262335", "accent": "#341c5c", "text": "#ffffff",
        "inactive": "#1a1a2e", "border": "#495495", "active": "#f92aad",
    },
    "components": {
        "msstyles": {"variants": sw_mss_variants},
        "themes": {"variants": sw_theme_variants},
        "wallpapers": {"variants": sw_wall_variants},
        "cursors": {"path": "cursors"},
    },
}
write_manifest(SW_DST, sw_manifest)


# ============================================================================
# THEME 2 — BlackIsBack
# ============================================================================
print("\n=== BlackIsBack ===")

BIB_SRC = Path(
    r"C:\Users\kyleh\Documents\Projects\2H24Themes\Themes\BlackIsBack for Windows 11 (by niivu)"
)
BIB_RTF = BIB_SRC / "Resources_Themes_Folder"
BIB_DST = THEMES_DIR / "BlackIsBack"
PREV_SRC = Path(r"C:\Users\kyleh\Documents\Projects\2H24Themes\Themes\__Theme Previews__")

cp(PREV_SRC / "BlackIsBack 22H2 - Preview 1 [niivu].png", BIB_DST / "preview.png")

bib_black_mss = ["Black-DASH", "Black-DOTS", "Black-LIN", "Black-Mac",
                 "Black-NU", "Black-Round", "Black-SLASH", "Black-Win"]
bib_dark_mss = ["Dark-DASH", "Dark-DOTS", "Dark-LIN", "Dark-Mac",
                "Dark-NU", "Dark-Round", "Dark-SLASH", "Dark-Win"]

for f in bib_black_mss:
    cp(BIB_RTF / "Black" / f"{f}.msstyles", BIB_DST / "msstyles" / "Black" / f"{f}.msstyles")
    cp(BIB_RTF / "Black" / f"{f} NA.msstyles", BIB_DST / "msstyles" / "Black" / f"{f} NA.msstyles")
for f in bib_dark_mss:
    cp(BIB_RTF / "Dark" / f"{f}.msstyles", BIB_DST / "msstyles" / "Dark" / f"{f}.msstyles")
    cp(BIB_RTF / "Dark" / f"{f} NA.msstyles", BIB_DST / "msstyles" / "Dark" / f"{f} NA.msstyles")

for f in bib_black_mss:
    cp(BIB_RTF / f"{f}.theme", BIB_DST / "themes" / f"{f}.theme")
    cp(BIB_RTF / f"{f} NA.theme", BIB_DST / "themes" / f"{f} NA.theme")
for f in bib_dark_mss:
    cp(BIB_RTF / f"{f}.theme", BIB_DST / "themes" / f"{f}.theme")
    cp(BIB_RTF / f"{f} NA.theme", BIB_DST / "themes" / f"{f} NA.theme")

bib_walls = ["DASH.jpg", "DOTS.jpg", "LIN.jpg", "MAC.jpg",
             "NU.jpg", "Round.jpg", "Slash.jpg", "WIN.jpg"]
for f in bib_walls:
    cp(BIB_RTF / "Black" / "Wallpapers" / f, BIB_DST / "wallpapers" / f)

bib_mss_variants = (
    [{"name": f"Black - {s.replace('Black-', '')}", "file": f"msstyles/Black/{s}.msstyles"} for s in bib_black_mss]
    + [{"name": f"Dark - {s.replace('Dark-', '')}", "file": f"msstyles/Dark/{s}.msstyles"} for s in bib_dark_mss]
)
bib_theme_variants = (
    [{"name": f"Black - {s.replace('Black-', '')}", "file": f"themes/{s}.theme"} for s in bib_black_mss]
    + [{"name": f"Dark - {s.replace('Dark-', '')}", "file": f"themes/{s}.theme"} for s in bib_dark_mss]
)
bib_wall_variants = [{"name": os.path.splitext(f)[0], "file": f"wallpapers/{f}"} for f in bib_walls]

bib_manifest = {
    "name": "BlackIsBack",
    "version": "1.0.0",
    "description": "An ultra-dark monochromatic Windows 11 theme in Black and Dark variants by niivu.",
    "author": "niivu",
    "preview": "preview.png",
    "palette": {
        "background": "#0d0d0d", "accent": "#1a1a1a", "text": "#e0e0e0",
        "inactive": "#080808", "border": "#333333", "active": "#ffffff",
    },
    "components": {
        "msstyles": {"variants": bib_mss_variants},
        "themes": {"variants": bib_theme_variants},
        "wallpapers": {"variants": bib_wall_variants},
    },
}
write_manifest(BIB_DST, bib_manifest)


# ============================================================================
# THEME 3 — Paranoid Android
# ============================================================================
print("\n=== Paranoid Android ===")

PA_SRC = Path(
    r"C:\Users\kyleh\Documents\Projects\2H24Themes\Themes\Paranoid Android for Windodws 11 -  (by niivu)"
)
PA_RTF = PA_SRC / "Resources_Themes_Folder"
PA_VAR = PA_RTF / "Paranoid Android"
PA_DST = THEMES_DIR / "Paranoid Android"

cp(PA_SRC / "Paranoid Android Preview - niivu.png", PA_DST / "preview.png")

pa_mss_all = [
    "LUV.msstyles", "LUVMIN.msstyles", "LUVNA.msstyles",
    "LUV - Night.msstyles", "LUV - NightMIN.msstyles", "LUV - NightNA.msstyles",
    "Nebula.msstyles", "NebulaMIN.msstyles", "NebulaNA.msstyles",
    "Nebula - Night.msstyles", "Nebula - NightMIN.msstyles", "Nebula - NightNA.msstyles",
    "Sweet.msstyles", "SweetMIN.msstyles", "SweetNA.msstyles",
    "Sweet - Night.msstyles", "Sweet - NightMIN.msstyles", "Sweet - NightNA.msstyles",
]
for f in pa_mss_all:
    cp(PA_VAR / f, PA_DST / "msstyles" / f)

pa_themes_all = [
    "Paranoid Android - LUV - dark MIN.theme", "Paranoid Android - LUV - dark NA.theme",
    "Paranoid Android - LUV - dark.theme", "Paranoid Android - LUV - light MIN.theme",
    "Paranoid Android - LUV - light NA.theme", "Paranoid Android - LUV - light.theme",
    "Paranoid Android - LUV - night MIN.theme", "Paranoid Android - LUV - night NA.theme",
    "Paranoid Android - LUV - night.theme", "Paranoid Android - Nebula - dark MIN.theme",
    "Paranoid Android - Nebula - dark NA.theme", "Paranoid Android - Nebula - dark.theme",
    "Paranoid Android - Nebula - light MIN.theme", "Paranoid Android - Nebula - light NA.theme",
    "Paranoid Android - Nebula - light.theme", "Paranoid Android - Nebula - night MIN.theme",
    "Paranoid Android - Nebula - night NA.theme", "Paranoid Android - Nebula - night.theme",
    "Paranoid Android - Sweet - dark MIN.theme", "Paranoid Android - Sweet - dark NA.theme",
    "Paranoid Android - Sweet - dark.theme", "Paranoid Android - Sweet - light MIN.theme",
    "Paranoid Android - Sweet - light NA.theme", "Paranoid Android - Sweet - light.theme",
    "Paranoid Android - Sweet - night MIN.theme", "Paranoid Android - Sweet - night NA.theme",
    "Paranoid Android - Sweet - night.theme",
]
for f in pa_themes_all:
    cp(PA_RTF / f, PA_DST / "themes" / f)

pa_walls = ["Paranoid Android - LUV.png", "Paranoid Android - Nebula.png",
            "Paranoid Android - Sweet.png", "Paranoid Android - Sweetspot.png"]
for f in pa_walls:
    cp(PA_VAR / "Wallpapers" / f, PA_DST / "wallpapers" / f)

pa_mss_variants = [
    {"name": "LUV", "file": "msstyles/LUV.msstyles"},
    {"name": "LUV Night", "file": "msstyles/LUV - Night.msstyles"},
    {"name": "Nebula", "file": "msstyles/Nebula.msstyles"},
    {"name": "Nebula Night", "file": "msstyles/Nebula - Night.msstyles"},
    {"name": "Sweet", "file": "msstyles/Sweet.msstyles"},
    {"name": "Sweet Night", "file": "msstyles/Sweet - Night.msstyles"},
]
pa_theme_variants = [
    {"name": "LUV - Dark", "file": "themes/Paranoid Android - LUV - dark.theme"},
    {"name": "LUV - Light", "file": "themes/Paranoid Android - LUV - light.theme"},
    {"name": "LUV - Night", "file": "themes/Paranoid Android - LUV - night.theme"},
    {"name": "Nebula - Dark", "file": "themes/Paranoid Android - Nebula - dark.theme"},
    {"name": "Nebula - Light", "file": "themes/Paranoid Android - Nebula - light.theme"},
    {"name": "Nebula - Night", "file": "themes/Paranoid Android - Nebula - night.theme"},
    {"name": "Sweet - Dark", "file": "themes/Paranoid Android - Sweet - dark.theme"},
    {"name": "Sweet - Light", "file": "themes/Paranoid Android - Sweet - light.theme"},
    {"name": "Sweet - Night", "file": "themes/Paranoid Android - Sweet - night.theme"},
]
pa_wall_variants = [
    {"name": os.path.splitext(f)[0].replace("Paranoid Android - ", ""), "file": f"wallpapers/{f}"}
    for f in pa_walls
]

pa_manifest = {
    "name": "Paranoid Android",
    "version": "1.0.0",
    "description": "A Catppuccin-inspired dark blue Windows 11 theme in LUV, Nebula, and Sweet variants by niivu.",
    "author": "niivu",
    "preview": "preview.png",
    "palette": {
        "background": "#1c2333", "accent": "#252f43", "text": "#cdd6f4",
        "inactive": "#161b27", "border": "#45475a", "active": "#89b4fa",
    },
    "components": {
        "msstyles": {"variants": pa_mss_variants},
        "themes": {"variants": pa_theme_variants},
        "wallpapers": {"variants": pa_wall_variants},
    },
}
write_manifest(PA_DST, pa_manifest)


# ============================================================================
# THEME 4 — DRK 25
# ============================================================================
print("\n=== DRK 25 ===")

DRK_SRC = Path(r"C:\Users\kyleh\Documents\Projects\2H24Themes\Themes\DRK 25 by niivu")
DRK_RTF = DRK_SRC / "Resources_Themes_Folder"
DRK_DST = THEMES_DIR / "DRK 25"

cp(DRK_SRC / "DRK 25 by niivu.png", DRK_DST / "preview.png")

# DRK 25 msstyles prefix per button style:
# MAC prefix = DRK3, SQR prefix = DRK2, WIN prefix = DRK
drk_prefixes = {"MAC": "DRK3", "SQR": "DRK2", "WIN": "DRK"}
drk_suffixes = ["25", "25b"]
drk_variant_labels = ["Normal", "NoAccent"]

drk_mss_files = []
drk_theme_files = []
for style_key, prefix in drk_prefixes.items():
    for suffix in drk_suffixes:
        for variant_label in drk_variant_labels:
            na_tag = "NA" if variant_label == "NoAccent" else ""
            base = f"{prefix}{suffix}{na_tag}"
            drk_mss_files.append({
                "name": f"{style_key} {suffix} {variant_label}",
                "file": f"msstyles/{style_key}/{base}.msstyles",
                "style": style_key,
                "filename": f"{base}.msstyles",
            })
            drk_theme_files.append({
                "name": f"{style_key} {suffix} {variant_label}",
                "file": f"themes/{base}.theme",
                "filename": f"{base}.theme",
            })

for entry in drk_mss_files:
    cp(DRK_RTF / entry["style"] / entry["filename"], DRK_DST / entry["file"])

for entry in drk_theme_files:
    cp(DRK_RTF / entry["filename"], DRK_DST / entry["file"])

drk_walls = ["25 by niivu.png", "25 NIght by niivu.png"]
for f in drk_walls:
    cp(DRK_RTF / "MAC" / "Wallpapers" / f, DRK_DST / "wallpapers" / f)

drk_mss_variants = [{"name": e["name"], "file": e["file"]} for e in drk_mss_files]
drk_theme_variants = [{"name": e["name"], "file": e["file"]} for e in drk_theme_files]
drk_wall_variants = [{"name": os.path.splitext(f)[0], "file": f"wallpapers/{f}"} for f in drk_walls]

drk_manifest = {
    "name": "DRK 25",
    "version": "1.0.0",
    "description": "A dark Windows 11 theme with MAC, SQR, and WIN button styles in 25 and 25b variants by niivu.",
    "author": "niivu",
    "preview": "preview.png",
    "palette": {
        "background": "#0a0a0a", "accent": "#1a1a2e", "text": "#e8e8e8",
        "inactive": "#050505", "border": "#2a2a2a", "active": "#888888",
    },
    "components": {
        "msstyles": {"variants": drk_mss_variants},
        "themes": {"variants": drk_theme_variants},
        "wallpapers": {"variants": drk_wall_variants},
    },
}
write_manifest(DRK_DST, drk_manifest)

print("\n=== Setup Complete ===")
print(f"Themes written to: {THEMES_DIR}")