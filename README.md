# ThemeLauncher

> A 17-agent desktop theming engine for Windows. Mix, apply, and auto-heal
> your rice — and stop losing it to every Windows Update.

ThemeLauncher is a theming application built for the Windows ricing
community. It unifies msstyles visual styles, cursors, icons, wallpapers,
StartAllBack, OldNewExplorer, MicaForEveryone, Windhawk and legacy 7TSP
icon packs behind a single programmatic engine, and keeps your desktop
looking the way you set it — even after Microsoft's updates try to wipe it.

![status](https://img.shields.io/badge/platform-Windows%2010%2F11-blue)
![status](https://img.shields.io/badge/python-3.10%2B-blue)
![status](https://img.shields.io/badge/license-MIT-green)

---

## Why ThemeLauncher

Ricing on Windows has always been a chore of half-broken tools: a cursor
patcher here, an icon packager there, a visual-style installer that hasn't
been updated since 2016 — and every cumulative Windows Update silently
reverts half of it. ThemeLauncher exists to fix that.

- **Update Resilience** — watches the Windows Update event log, verifies your
  themed components are still intact, and silently re-applies anything an
  update overwrote. You stop noticing updates exist.
- **Theme Mixer** — stop choosing. Borrow msstyles from one theme, cursors
  from another, wallpaper from a third, and save the combination as your own.
- **7TSP → Windhawk** — a decade of legacy 7TSP icon packs, resurrected. The
  extractor remaps `.res`→`.dll` (with PE validation) and stages icons for
  Windhawk's Resource Redirect.
- **Variant Engine** — derive `dark`, `light` and `slate` variants from any
  palette via HSV recoloring, skipping variants the theme already ships.
- **Snapshots & Smart Rollback** — every apply is preceded by a registry +
  file snapshot. One click restores your system from any point in time.
- **Scheduled Switching** — cron-style rules plus circadian suggestions. Wake
  to a light rice, go dark at sunset.

---

## Screenshots / Modes

ThemeLauncher has three modes, switchable from the sidebar (or `Ctrl+1/2/3`):

| Mode | What it's for |
|------|---------------|
| **Presets** | One-click curated themes with a live preview and per-component controls. |
| **Mixer** | Cross-theme Frankenstein — slot components from any theme, save as new. |
| **Studio** | Asset-level control: browse, recolour, and install icon & cursor sets. |

---

## Getting started

### Prerequisites

- **Windows 10 or 11** (the app uses `winreg`, `ctypes.windll`, `setupapi`,
  and `wevtutil` — it will not run on Linux/macOS).
- **Python 3.10+**
- **Administrator privileges** for full functionality (font installation,
  system file replacement, Windhawk resource deployment). Launch with the
  `--admin` flag to trigger the UAC prompt automatically.

### Install

```bash
git clone https://github.com/baldest-eagle/themelauncher.git
cd themelauncher
pip install -r requirements.txt
```

> **Optional:** `pip install py7zr` enables `.7z` / 7TSP SFX `.exe` archive
> extraction and icon-pack packaging. Without it, `.zip`/`.tar` archives still
> work.

### Configure

Create a `config.json` in the project root:

```json
{
  "themes_directory": "C:\\Users\\you\\Themes",
  "active_theme": "SynthWave '84"
}
```

### Run

```bash
python main.py              # normal launch
python main.py --admin      # launch with an elevation prompt
```

The app starts the **Update Resilience Monitor** and the **Theme Scheduler**
as background daemon threads automatically, and stops them gracefully on exit.

---

## The 17-agent engine

ThemeLauncher is built as a facade (`ThemeSDK`) over 17 lazily-initialized
agents. Every method follows the `{"success": bool, "message": str, ...}`
return convention.

### Tier 1 — Critical

| Agent | Role |
|-------|------|
| **Update Resilience** | Monitors Windows Update events and auto-heals overwritten components. |
| **Snapshot** | Captures registry + file baselines before any change for rollback. |
| **Variant Generator** | Derives `dark` / `light` / `slate` palettes via HSV recoloring. |
| **Theme Mixer** | Combines components across themes; persists the result. |
| **Theme Scheduler** | Cron-style theme rotation with circadian suggestions. |
| **Compatibility** | Pre-flight checks so a broken theme never half-applies. |

### Tier 2 — High value

| Agent | Role |
|-------|------|
| **7TSP Extractor** | Converts legacy 7TSP icon packs to Windhawk format. |
| **Icon Pack Converter** | Maps icon filenames to system DLL resource indices. |
| **Manifest Generator** | Auto-generates manifests for loose theme folders. |
| **Recommender** | Palette-similarity + circadian theme suggestions. |
| **Community Index** | Crawl & search community theme sources. |
| **Diff Engine** | Diff two manifests to see exactly what changes. |
| **Accessibility Checker** | WCAG 2.1 contrast reports for any palette. |
| **Performance Analyzer** | Benchmark the cost of a component before committing. |
| **Theme Packager** | Package a theme for distribution & publishing. |
| **Directory Auditor** | Audit & standardize messy theme folder structures. |
| **Crash Monitor** | Track & summarize errors across sessions. |

### Programmatic usage

```python
from themelauncher.sdk import ThemeSDK

sdk = ThemeSDK(config_path="config.json")

# Apply a full theme (snapshot is captured automatically before apply)
result = sdk.apply_theme("Tokyo Night")
print(result["success"], result["message"])

# List & restore snapshots
snaps = sdk.list_snapshots()
sdk.restore_snapshot(snaps[-1]["id"])

# Generate variants
sdk.generate_variants("Tokyo Night", palette, types=["dark", "slate"])

# Convert a 7TSP pack
sdk.extract_7tsp("SynthWave_7tsp.7z", "SynthWave Icons")
```

---

## Theme manifest format

A theme is a folder under `themes_directory` containing a `manifest.json`:

```json
{
  "name": "Tokyo Night",
  "version": "1.0.0",
  "author": "enkia",
  "description": "Rainy neon Tokyo at night.",
  "palette": {
    "background": "#1a1b26",
    "accent": "#7aa2f7",
    "text": "#c0caf5",
    "inactive": "#16161e",
    "border": "#414868",
    "active": "#7aa2f7"
  },
  "components": {
    "msstyles":  { "variants": [ { "name": "Dark", "file": "TokyoNight.msstyles" } ] },
    "wallpapers":{ "variants": [ { "name": "Rain",  "file": "rain.png", "preview": "rain.png" } ] },
    "cursors":   { "path": "cursors", "scheme_name": "Tokyo Night" },
    "startallback": { "guide": "startallback", "app": "startallback" },
    "mica":      { "settings_json": "mica/settings.json", "guide": "mica" }
  }
}
```

The GUI itself is **theme-reactive**: when you select a theme, the entire UI
recolors to match that theme's palette via `ThemeColors`.

---

## Safety

- Every apply is preceded by a registry + file snapshot. Rollback is one click.
- If a snapshot exists, Smart Rollback prefers restoring from it over static
  system defaults.
- The Update Resilience monitor restores from snapshots — never from hardcoded
  defaults — so your *actual* baseline is what comes back.
- Administrator privileges are clearly warned about at startup if absent; the
  specific operations that require elevation (fonts, system files) are skipped
  with a logged warning rather than crashing.

---

## Keyboard shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+1` | Presets mode |
| `Ctrl+2` | Mixer mode |
| `Ctrl+3` | Studio mode |
| `Ctrl+S` | Save current mix (in Mixer mode) |
| `Ctrl+Shift+R` | Emergency palette reset (escapes an unreadable theme) |
| `Esc` | Close dialog |

---

## Project structure

```
themelauncher/
├── main.py                     # Entry point (handles --admin elevation)
├── config.json                 # Themes directory + active theme
├── core/                       # Core engine
│   ├── _io.py                  #   Atomic writes, safe_remove, retry helpers
│   ├── win32.py                #   Windows API shim (reg_open_key, SPI, guards)
│   ├── applier.py              #   Applies theme components to the system
│   ├── theme_manager.py        #   Discovers, imports, deletes themes
│   ├── manifest_parser.py      #   Parses + validates manifest.json
│   ├── mixer.py                #   Cross-theme component mixing
│   ├── theme_colors.py         #   Theme-reactive palette + contrast guards
│   ├── asset_studio.py         #   Icon/cursor set management + recolouring
│   └── logger.py               #   Rotating-file logger
├── themelauncher/              # The 17-agent SDK
│   ├── sdk.py                  #   ThemeSDK facade
│   ├── core/logger.py          #   SDK logger
│   └── agents/                 #   The 17 agents (see table above)
├── ui/                         # CustomTkinter GUI
│   ├── app.py                  #   Main window (3 modes, status bar, async)
│   ├── theme_card.py           #   Theme card in the sidebar
│   ├── preview_panel.py        #   Live preview
│   ├── component_panel.py      #   Per-component variant controls
│   ├── mixer_panel.py          #   Mixer slot grid
│   ├── mix_recipe_panel.py     #   Mix recipe + save-as-theme
│   ├── asset_studio_panel.py   #   Icon/cursor studio (tabs)
│   ├── guide_dialog.py         #   Setup-guide walkthrough
│   └── tooltip.py              #   Lightweight hover tooltip helper
└── assets/                     # Default theme + placeholder art
```

---

## Contributing

Contributions are welcome. Areas that especially need help:

- **Windhawk mod management** (enable/disable mods, not just icon files).
- **Terminal theming** for WezTerm and Alacritty (see `INTEGRATIONS.md`).
- **GlazeWM / Komorebi** status-bar config sync.
- More cursor-pack format importers (CursorFX, RWCursor).

See [`INTEGRATIONS.md`](INTEGRATIONS.md) for a full ranked list of suggested
integrations and [`task_plan.md`](task_plan.md) for the roadmap.

---

## License

MIT
