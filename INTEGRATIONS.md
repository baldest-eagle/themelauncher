# Integration Suggestions for ThemeLauncher

These are concrete integrations that would benefit ricers and make
ThemeLauncher a more compelling paid product. They are ranked by
**impact-to-effort ratio** based on the current 17-agent architecture.
Each suggestion notes which existing agent it extends and whether it is a
quick win or a larger project.

---

## Tier 1 — High impact, leverages existing architecture

### 1. Windhawk mod sync (extends `compatibility.py`, `update_resilience.py`)
**Why:** Windhawk is the modern modding platform ricers actually use. Right now
ThemeLauncher deploys icon *files* to Windhawk's Resources dir, but doesn't
enable/manage the **Windhawk mods** themselves (e.g. "Resource Redirect",
"Taskbar height and icon size", "Classic Explorer").

**What to build:**
- A `WindhawkSync` agent that reads the active theme's manifest for a
  `windhawk.mods` list (mod IDs + desired settings JSON), enables each mod via
  Windhawk's ModsWritable JSON, and applies the settings.
- The `UpdateResilience` agent already checks `ModsWritable` is non-empty —
  extend `check_integrity` to diff the *enabled mod set* against the snapshot,
  so a Windows Update that disables a mod gets auto-re-enabled.

**Effort:** Medium. Windhawk's mod config is plain JSON in
`%APPDATA%\Windhawk\ModsWritable\<mod-id>\config.json`. No IPC needed.

### 2. GlazeWM / Komorebi status-bar theming (new `bar_sync.py` agent)
**Why:** A huge fraction of ricers on Windows now run **GlazeWM** or
**Komorebi** (tiling WMs) with a YAML/JSON config. ThemeLauncher themes the
*desktop* but not the *bar* — so a fresh theme leaves the bar clashing.

**What to build:**
- An agent that maps the active palette → GlazeWM `config.yaml` color block
  (background, foreground, accent, urgent, focused-workspace colors) and
  triggers a config reload.
- Add a `bar` component type to the manifest parser so a theme can ship a
  ready-made bar config.

**Effort:** Small-to-medium. GlazeWM reloads on file change. The palette→YAML
mapping is ~40 lines.

### 3. WezTerm / Windows Terminal profile injection (extends `applier._apply_terminal`)
**Why:** Terminal theming is the #1 thing ricers share. ThemeLauncher already
patches Windows Terminal `settings.json`, but **WezTerm** (increasingly
popular) and **Alacritty** are unsupported.

**What to build:**
- A `TerminalSync` agent that detects installed terminals and writes the
  theme's color scheme into the right file for each:
  - WezTerm: emit a Lua color scheme into `~/.config/wezterm/colors/` and add
    it to the active config.
  - Alacritty: write a `*.toml` (Alacritty 0.13+) or `*.yml` to the themes dir.
- Expose via the SDK as `sdk.sync_terminals(theme_name)`.

**Effort:** Small. Each is a palette→format serializer.

### 4. Wallpaper Engine / lively wallpaper integration (extends `applier._apply_wallpaper`)
**Why:** Static wallpapers are table stakes. Ricers increasingly use animated
wallpapers via **Lively Wallpaper** (open source) or Wallpaper Engine.

**What to build:**
- A `wallpaper` component variant type `"animated"` that, when present, sets
  the wallpaper through Lively's CLI (`lively.exe --set-wallpaper <path>`)
  instead of `SystemParametersInfoW`.
- Fall back to a static poster frame for the active theme when Lively isn't
  installed.

**Effort:** Small. One subprocess call + manifest field.

### 5. CursorFX / RWCursor pack import (extends `seven_tsp_extractor.py`)
**Why:** The 7TSP extractor already resurrects one legacy icon format. There's
a parallel ecosystem of **CursorFX** (`.cursorfx`) and **RWCursor** cursor
packs that ricers have lying around.

**What to build:**
- Extend the extractor's `_unpack_archive` dispatch to handle `.cursorfx`
  (which is a renamed zip containing `.cur`/`.ani` + an `info.xml`).
- Map the XML's role definitions onto `CURSOR_ROLES` and stage into the
  theme's `cursors/` folder.

**Effort:** Small. The `.cursorfx` format is documented and just a zip.

---

## Tier 2 — Differentiators that justify a paid tier

### 6. Ricing "profiles" / scene presets (extends `scheduler.py`, `packager.py`)
**Why:** Ricers love showing off. A **profile** is a named, exportable bundle
of (theme + bar config + terminal scheme + wallpaper + Windhawk mod state).
One click swaps your entire *scene*; another restores it.

**What to build:**
- A `ProfileManager` agent that snapshots the full themed state (not just
  registry — also the Windhawk mods, terminal schemes, bar config) into a
  `.themeprofile` archive.
- The existing `ThemePackager` can be reused to zip it.
- The `ThemeScheduler` can fire profile swaps (not just theme swaps) on cron.

**Effort:** Medium. Mostly aggregation of existing snapshot logic.

### 7. Auto-palette extraction from any wallpaper (extends `manifest_generator.py`)
**Why:** The `ManifestGenerator` already runs k-means on a wallpaper to derive
a palette. Wire it into a **"Match UI to wallpaper"** button: pick any image,
ThemeLauncher derives a coherent palette, generates light/dark/slate variants
via the `VariantGenerator`, and applies them to msstyles accent + terminal +
bar in one shot.

**What to build:**
- A UI action `sdk.match_to_wallpaper(image_path)` that chains
  `ManifestGenerator.extract_palette` → `VariantGenerator.generate_variants`
  → apply.
- ~~Seed the k-means (the audit flagged it as unseeded) for reproducibility.~~
  **Done** — `manifest_generator.py` now uses `np.random.default_rng(42)`.
  Only the UI action + chaining remains.

**Effort:** Small. Most pieces exist; it's a composition + UI button.

### 8. Spotify / now-playing reactive theming (extends `scheduler.py`)
**Why:** "My desktop shifts hue with the album art" is a killer demo for
selling to ricers.

**What to build:**
- A `NowPlayingAgent` that polls the album-art color (via the Windows
  MediaTransport API or Spotify's local web helper) every few seconds and,
  when it changes meaningfully, nudges the active accent color via the
  `VariantGenerator.derive_hue_shift`.
- Gate behind a "Reactive mode" toggle so it's opt-in.

**Effort:** Medium. Polling + throttled apply (don't re-apply the whole theme;
only the accent registry key + a `WM_SETTINGCHANGE` broadcast).

### 9. Rainmeter skin bundling (new component type)
**Why:** Rainmeter is still huge in the ricing scene. A theme that ships a
matching Rainmeter layout is dramatically more polished.

**What to build:**
- A `rainmeter` component type in the manifest parser. On apply, copy the
  skin folder to `Documents\Rainmeter\Skins\` and write an `Active=1` line to
  `Rainmeter.ini` for the included layout.

**Effort:** Small. Rainmeter's layout is a simple INI.

---

## Tier 3 — Community / distribution (helps it become a product)

### 10. One-click theme install from a URL (extends `community_index.py`)
**Why:** The `CommunityIndex` agent exists but only *crawls & searches*. Make
it actionable: a ricer pastes a GitHub/Reddit theme URL, ThemeLauncher
downloads, extracts, audits, and installs it.

**What to build:**
- A `install_from_url(url)` SDK method that resolves a GitHub release asset or
  a direct archive, downloads to temp, and feeds it to the existing
  `import_theme_folder` / `SevenTSPExtractor` pipeline based on content type.
- Sandboxed extraction (audit for unexpected `.exe`/`.bat` before staging).

**Effort:** Medium. HTTP + the existing extraction pipeline.

### 11. Theme store / registry (extends `packager.py`, `publish_theme`)
**Why:** `publish_theme` now returns a clear `{"success": False, "message":
"Publishing is not yet implemented..."}` so callers aren't fooled into
thinking a publish succeeded — but there's still no real backend. A
lightweight, self-hostable theme registry (even just a GitHub repo of
`.themeprofile` files with an index JSON) turns the app into a platform.

**What to build:**
- Implement `publish_theme` to push a packaged theme to a configured Git repo
  via `git` CLI (no API keys needed for public repos).
- The `CommunityIndex` reads that repo's index as a browsable catalog inside
  the app.

**Effort:** Medium. Mostly git plumbing + a browse UI in Studio mode.

### 12. Diff-based theme sharing (extends `diff_engine.py`)
**Why:** The `DiffEngine` diffs manifests but the output isn't actionable.
Ricers want to share *just the delta* ("here's my SynthWave cursor swap for
Tokyo Night").

**What to build:**
- A `export_mix_as_patch` that produces a small `.themepatch` containing only
  the changed components + a base-theme reference. Double-clicking a
  `.themepatch` applies it on top of the named base.

**Effort:** Small. Reuses `Mixer.save_as_theme` with a "base" reference field.

---

## Cross-cutting improvements

Two of the three foundations the audit recommended are now in place; the
third remains open.

- ✅ **`core/win32.py` shim** — **built**. Centralizes `winreg`/`ctypes.windll`
  access behind lazy imports + a `reg_open_key` context manager (auto-`CloseKey`
  in `finally`) + `set_system_parameter` (checks the `SystemParametersInfoW`
  return code). Every integration above can use it; the handle-leak and
  import-safety bug classes are closed.
- ✅ **Atomic file writes** — **built** as `core/_io.py` (`atomic_write`,
  `atomic_write_json`, `safe_remove`, `retry`). config.json, icon_sets.json,
  manifest.json, terminal settings, and snapshots all write atomically now
  (temp file + `os.replace`). New integrations should use `atomic_write_json`
  for any config file they touch (Windhawk mod JSON, Rainmeter.ini, GlazeWM
  config, etc.).
- ⬜ **A typed manifest schema** (Pydantic or dataclasses): the manifest parser
  still trusts arbitrary dicts. A schema would make adding new component types
  (bar, terminal, rainmeter, animated wallpaper) safe and self-documenting, and
  would let the validator catch malformed manifests before they reach the
  applier. This is the single highest-leverage remaining foundation item.

---

## Recommended priority for a paid launch

If the goal is to sell to ricers, ship these first:

1. **Windhawk mod sync** (#1) — without it, the headline "works with Windhawk"
   is only half-true.
2. **GlazeWM/Komorebi bar theming** (#2) — the single most-requested feature
   in ricing communities right now.
3. **Auto-palette-from-wallpaper** (#7) — the best 30-second demo for a
   landing page / r/unixporn post.
4. **Reactive now-playing theming** (#8) — the "wow" feature that justifies a
   Pro tier on its own.
5. **One-click install from URL** (#10) — removes the friction that stops
   people from actually using community themes.

These five turn ThemeLauncher from "a theming app" into "the theming platform
for Windows" — and give you clear Pro-tier differentiators.
