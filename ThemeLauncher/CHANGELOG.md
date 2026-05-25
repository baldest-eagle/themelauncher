# Changelog — Theme Launcher Integration & Enhancements

All changes completed today (May 24, 2026) to integrate the 15-agent programmatic SDK facade, wire up desktop customized automation and safety layers, and refine the color variant engine.

---

## 🚀 Key Highlights

* **Unified App Startup**: Wired `main.py` directly into the `ThemeSDK` facade, establishing a single programmatic core.
* **Resilience & Automation**: Spin up the **Windows Update Resilience Monitor** and **Theme Scheduler** as background daemon threads at startup.
* **Safety Snapshots**: Automatically record system baseline snapshots via the **Snapshot Agent** before any registry or file customization is applied.
* **Resilient Smart Rollback**: Prioritize smart rollback of system-wide customizations from snapshots over static hardcoded system defaults.
* **Variant Duplication Prevention**: The **Variant Generator** now intelligently skips generating `light`, `dark`, or `slate` variants if they are already provided in the theme's manifest or files.

---

## 🛠️ Detailed File Changes

### 1. `themelauncher/sdk.py` (Unified Facade)
* Exposed the public property `@property def theme_manager(self)` to lazily instantiate and expose the underlying core `ThemeManager`.
* Cleanly bridged component discovery and metadata requests to make `ThemeSDK` a drop-in replacement for the launcher's GUI.

### 2. `main.py` (Application Entry Point)
* Replaced direct imports of `ThemeManager` with `ThemeSDK` initialization.
* Added safe error handling for missing `config.json` configurations.
* **Daemon Execution**: Spawned background threads for Windows Update Resilience and Cron Scheduling.
* Cleanly passed the SDK context to the GUI launcher.
* **Graceful Teardown**: Programmed `sdk.stop_scheduler()` to close background loops gracefully on application shutdown.

### 3. `ui/app.py` (CustomTkinter GUI)
* **Constructor Overload**: Upgraded the constructor to gracefully support both the new `ThemeSDK` context and raw legacy `ThemeManager` instances.
* **Defensive Snapshots**: Wired a pre-flight hook in `_on_apply()` that automatically captures a registry/settings snapshot before any theme or separate component is applied.
* **Smart Rollback Integration**: Overloaded `_restore_system_defaults()` to prioritize registry and file restoration from captured baseline snapshots. Falls back to static file replacement only if no snapshots exist.

### 4. `themelauncher/agents/variant_generator.py` (Variant Generator Agent)
* **Scope Restriction**: Restricted variant generation exclusively to three target types: `light`, `dark`, and `slate`.
* **Premium Muted Slate Variant**: Added `derive_slate_palette()`, which shifts theme palettes to a premium muted bluish-gray slate tone using HSL scaling.
* **Duplicate Detection**: Implemented `_is_variant_provided()`, which checks:
  1. The theme's `manifest.json` for variant lists with names or file paths matching `light`, `dark`, or `slate`.
  2. The theme's folder recursively for existing files containing `light`, `dark`, or `slate` in their filename.
* **Conditional Generation**: Automatically skips generating any target variant already present in the provided files to prevent file conflicts and duplicate options in the UI.

### 5. `config.json` (Configuration)
* Standardized the `themes_directory` setting to the absolute path `C:\\Users\\kyleh\\.gemini\\themes`.
* This allows all 16 copied premium customizer themes (such as SynthWave '84, Paranoid Android, Tokyo Night, and DRK 25) to load instantly into the application.

---

## 🔍 Verification Summary
All changes have been successfully verified inside the local `win32` Python environment:
* Checked imports, syntax correctness, and initialization.
* Confirmed background thread stability.
* Verified manifest scanning and file checks skip existing variants and successfully derive custom slate variant configurations.