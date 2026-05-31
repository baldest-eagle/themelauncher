# Missing Assets Tracker

Drop files into the correct theme folder and the launcher will pick them up automatically.
Update the status column here when done.

---

## Legend
- `preview.png` → theme root (e.g. `themes/Tokyo Night/preview.png`)
- SAB skin → `themes/<Name>/startallback/<name>.SAB.msstyles`
- SAB guide images → `themes/<Name>/guides/startallback/*.png`
- Mica guide images → `themes/<Name>/guides/mica/*.png`
- ONE guide images → `themes/<Name>/guides/oldnewexplorer/*.png`
- Shortcut icons → `themes/extras/` or `themes/<Name>/icons/`

---

## Automation Status (2026-05-30)

### Implemented Features
- ✅ **Directory Auditor** - Theme folder structure validation
- ✅ **7TSP Extractor** - Legacy icon pack to Windhawk conversion  
- ✅ **SFC Background Thread** - Elevated system file checker with privilege handling
- ✅ **MicaForEveryone Auto-Apply** - JSON-based settings deployment
- ✅ **StartAllBack Auto-Apply** - Registry-based settings deployment

### Available Commands
```
python -m themelauncher.cli.main audit                  # Audit all themes
python -m themelauncher.cli.main extract-7tsp <archive> <theme>  # Convert 7TSP
python -m themelauncher.cli.main run-sfc              # Run SFC scan
```

---

## Per-Theme Gaps

### BlackIsBack
| Asset | Status |
|---|---|
| `preview.png` | ✅ sourced from `__Theme Previews__` |
| SAB skin (`.SAB.msstyles`) | ➖ N/A — not included in niivu's BlackIsBack pack |
| SAB guide screenshots | ⬜ pending — drop PNGs into `guides/startallback/` |
| Mica guide screenshots | ⬜ pending — drop PNGs into `guides/mica/` |
| OldNewExplorer guide screenshots | ⬜ pending — drop PNGs into `guides/oldnewexplorer/` |

### Buuf OS2
| Asset | Status |
|---|---|
| `preview.png` | ✅ sourced from `__Theme Previews__` |
| SAB skin (`.SAB.msstyles`) | ➖ N/A — not included in niivu's Buuf OS2 pack |
| SAB guide screenshots | ⬜ pending — drop PNGs into `guides/startallback/` |
| Mica guide screenshots | ⬜ pending — drop PNGs into `guides/mica/` |
| OldNewExplorer guide screenshots | ⬜ pending — drop PNGs into `guides/oldnewexplorer/` |

### Delta v1
| Asset | Status |
|---|---|
| `preview.png` | ✅ copied from `msstyles/Previews/Dark.png` |
| SAB skin (`.SAB.msstyles`) | ➖ N/A — not included in Delta v1 pack |
| SAB guide screenshots | ⬜ pending — drop PNGs into `guides/startallback/` |
| Mica guide screenshots | ⬜ pending — drop PNGs into `guides/mica/` |
| OldNewExplorer guide screenshots | ⬜ pending — drop PNGs into `guides/oldnewexplorer/` |

### Delta v2
| Asset | Status |
|---|---|
| `preview.png` | ✅ copied from `msstyles/Previews/Dark.png` |
| SAB skin (`.SAB.msstyles`) | ➖ N/A — not included in Delta v2 pack |
| SAB guide screenshots | ⬜ pending — drop PNGs into `guides/startallback/` |
| Mica guide screenshots | ⬜ pending — drop PNGs into `guides/mica/` |
| OldNewExplorer guide screenshots | ⬜ pending — drop PNGs into `guides/oldnewexplorer/` |

### DRK 25
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| SAB skin | ✅ `DRK 25 SAB.msstyles` |
| SAB guide | ✅ 1 image |
| Mica guide | ✅ 1 image |
| OldNewExplorer guide | ⬜ pending — drop PNG into `guides/oldnewexplorer/` |

### gruvbox
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| SAB skin | ➖ N/A — not included in gruvbox pack |
| SAB guide | ⬜ pending — drop PNGs into `guides/startallback/` |
| Mica guide | ⬜ pending — drop PNGs into `guides/mica/` |
| OldNewExplorer guide | ⬜ pending — drop PNGs into `guides/oldnewexplorer/` |

### iWin
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| `manifest.json` | ✅ created 2026-05-25 — covers 6 variants, 32 wallpapers, cursors, guide refs |
| SAB skin | ➖ N/A — not included in iWin pack |
| SAB guide | ⬜ pending — drop PNGs into `guides/startallback/` |
| Mica guide | ⬜ pending — drop PNGs into `guides/mica/` |
| OldNewExplorer guide | ⬜ pending — drop PNGs into `guides/oldnewexplorer/` |

### Janguru
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| SAB skin | ➖ N/A — not included in Janguru pack |
| SAB guide | ⬜ pending — drop PNGs into `guides/startallback/` |
| Mica guide | ⬜ pending — drop PNGs into `guides/mica/` |
| OldNewExplorer guide | ⬜ pending — drop PNGs into `guides/oldnewexplorer/` |

### Japan 26
| Asset | Status |
|---|---|
| `preview.png` | ✅ copied from `msstyles/JAPAN 26/Previews/JAPAN 26.png` |
| SAB guide | ✅ 2 images (Explorer, Taskbar) |
| Mica guide | ✅ 1 image |
| OldNewExplorer guide | ✅ 1 image |
| Custom shortcut icons (`japan26_*.ico`) | ⬜ original set missing — to be located |
| 7TSP icon pack | ✅ `icons/7TSP Japan26-area04.7z` |

### Kanagawa
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| SAB skin | ✅ 3 variants (DT, Lotus, Wave) |
| SAB guide | ✅ 3 images |
| Mica guide | ✅ 1 image |
| OldNewExplorer guide | ✅ 1 image |

### Kripton
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| SAB skin | ✅ |
| SAB guide | ✅ 1 image |
| Mica guide | ✅ 1 image |
| OldNewExplorer guide | ✅ 1 image |

### Night Owl
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| SAB skin | ➖ N/A — not included in Night Owl pack |
| SAB guide | ✅ 3 images |
| Mica guide | ✅ 2 images |
| OldNewExplorer guide | ✅ 1 image |

### Paranoid Android
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| SAB skin | ➖ N/A — not included in Paranoid Android pack |
| SAB guide | ⬜ pending — drop PNGs into `guides/startallback/` |
| Mica guide | ⬜ pending — drop PNGs into `guides/mica/` |
| OldNewExplorer guide | ⬜ pending — drop PNGs into `guides/oldnewexplorer/` |

### Rose Pine
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| SAB skin | ➖ N/A — not included in Rose Pine pack |
| SAB guide | ✅ 2 images |
| Mica guide | ✅ 1 image |
| OldNewExplorer guide | ✅ 1 image |

### Solarized
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| SAB skin | ➖ N/A — not included in Solarized pack |
| SAB guide | ⬜ pending — drop PNGs into `guides/startallback/` |
| Mica guide | ⬜ pending — drop PNGs into `guides/mica/` |
| OldNewExplorer guide | ⬜ pending — drop PNGs into `guides/oldnewexplorer/` |

### SynthWave 84
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| SAB skin | ✅ `SynthWave '84 SAB.msstyles` |
| SAB guide | ✅ 3 images |
| Mica guide | ✅ 1 image |
| OldNewExplorer guide | ✅ 1 image |

### Tokyo Night
| Asset | Status |
|---|---|
| `preview.png` | ✅ |
| SAB skin | ➖ N/A — not included in Tokyo Night pack |
| SAB guide | ⬜ pending — drop PNGs into `guides/startallback/` |
| Mica guide | ⬜ pending — drop PNGs into `guides/mica/` |
| OldNewExplorer guide | ⬜ pending — drop PNGs into `guides/oldnewexplorer/` |

---

## Global / Cross-Theme

### Custom Shortcut Icons (`themes/extras/`)
| Icon Set | Status | Notes |
|---|---|---|
| Japan 26 original `.ico` set | ⬜ missing | Generated versions exist (`japan26_*.ico`) but originals from niivu 7TSP pack not yet located |
| Amber variant icons | ✅ present | `amber_*.ico`, `bold_amber_*.ico` |
| Olive variant icons | ✅ present | `bold_olive_*.ico` |
| Kanagawa base icons | ✅ present | `firefox.ico`, `comet.ico`, etc. |
| Janguru icons | ✅ present | 3 sizes (17, 106, 144) |
| `japan26_7tsp/` folder | ⬜ empty | Staging folder for 7TSP pack — awaiting contents |

### Shortcut Icon Application
| Feature | Status |
|---|---|
| `shortcut_icons` component type in applier | ⬜ not yet built |
| `update_shortcuts.ps1` integration | ⬜ not yet wired into launcher |
| Icon pack generator integration | ⬜ not yet wired into launcher |

### MicaForEveryone Automation
| Feature | Status |
|---|---|
| Config file located | ✅ `%LOCALAPPDATA%\Packages\DongleInsovaki.MicaForEveryone_*\LocalState\settings.json` |
| JSON format understood | ✅ array of rules with `type`, `backdropPreference`, `titleBarColor`, etc. |
| Automation implemented | ⬜ not yet built — **fully automatable**, see notes below |

> **Note:** MicaForEveryone is actually fully automatable. Its `settings.json` is plain JSON and writable.
> Each theme needs a `mica/settings.json` file in its folder with the desired rule set.
> The applier just needs to find the package path and overwrite the file, then restart MFE.

### OldNewExplorer Automation
| Feature | Status |
|---|---|
| Registry key location confirmed | ⬜ key not found — may not be installed currently |
| Automation approach | ⬜ pending investigation when installed |

### StartAllBack Full Automation
| Feature | Status |
|---|---|
| Registry key structure mapped | ✅ `HKCU\Software\StartIsBack` — all dword/string values |
| Per-theme `.reg` export created | ⬜ not yet done for any theme |
| Applier support for `.reg` import | ⬜ not yet built |

> **Note:** SAB is automatable via registry import. Each theme needs a `startallback/settings.reg`
> exported from a configured SAB state. The applier can import it with `reg import`.
> This would eliminate the guide entirely for SAB.

---

## Manifest Status (2026-05-25)

All 17 themes now have `manifest.json` files with `startallback`, `mica`, and `oldnewexplorer`
component blocks pointing to their respective `guides/` subdirectories.

| Theme | manifest | guide dirs | SAB skin | SAB guide | Mica guide | ONE guide |
|---|---|---|---|---|---|---|
| BlackIsBack | ✅ | ✅ | ➖ N/A | ⬜ | ⬜ | ⬜ |
| Buuf OS2 | ✅ | ✅ | ➖ N/A | ⬜ | ⬜ | ⬜ |
| Delta v1 | ✅ | ✅ | ➖ N/A | ⬜ | ⬜ | ⬜ |
| Delta v2 | ✅ | ✅ | ➖ N/A | ⬜ | ⬜ | ⬜ |
| DRK 25 | ✅ | ✅ | ✅ | ✅ | ✅ | ⬜ |
| gruvbox | ✅ | ✅ | ➖ N/A | ⬜ | ⬜ | ⬜ |
| iWin | ✅ NEW | ✅ | ➖ N/A | ⬜ | ⬜ | ⬜ |
| Janguru | ✅ | ✅ | ➖ N/A | ⬜ | ⬜ | ⬜ |
| Japan 26 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Kanagawa | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Kripton | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Night Owl | ✅ | ✅ | ➖ N/A | ✅ | ✅ | ✅ |
| Paranoid Android | ✅ | ✅ | ➖ N/A | ⬜ | ⬜ | ⬜ |
| Rose Pine | ✅ | ✅ | ➖ N/A | ✅ | ✅ | ✅ |
| Solarized | ✅ | ✅ | ➖ N/A | ⬜ | ⬜ | ⬜ |
| SynthWave 84 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Tokyo Night | ✅ | ✅ | ➖ N/A | ⬜ | ⬜ | ⬜ |

---

## Quick Drop-In Instructions

When you find a missing file, just drop it in the right place:

**SAB skin:**
```
themes/<ThemeName>/startallback/<ThemeName> SAB.msstyles
```
Then add to manifest `components.startallback.skin`.

**SAB/Mica/ONE guide screenshot:**
```
themes/<ThemeName>/guides/startallback/  (or mica/ or oldnewexplorer/)
```
No manifest change needed — the launcher auto-discovers images in those folders.

**Root preview:**
```
themes/<ThemeName>/preview.png
```
Then update manifest `"preview": "preview.png"`.

**Japan 26 custom icons:**
```
themes/Japan 26/icons/  or  themes/extras/
```
Then update manifest `components.icons.variants`.