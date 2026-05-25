# Theme Launcher — Remaining Fixes Review

**Date**: May 25, 2026  
**Purpose**: Actionable fix list for a new agent to implement  
**Project Root**: `C:\Users\kyleh\.gemini\themelauncher`  
**Context**: A previous code review identified 24 findings. Most have been confirmed fixed in the actual codebase. This document covers only what is **still broken or incomplete**.

---

## Already Fixed (Do Not Touch)

The following are confirmed working in the real codebase — **skip these**:

- ✅ BUG-1: `_apply_msstyles()` uses registry broadcast + `SendMessageW` with fallback to `os.startfile`
- ✅ BUG-2: Cursor registry writes + `SPI_SETCURSORS` broadcast
- ✅ BUG-3: Font elevation warning on `PermissionError`
- ✅ BUG-4: No double discovery on startup
- ✅ BUG-5: Folder-type components handled in `set_active_theme()`
- ✅ BUG-6: Mixer variant append (no overwrite)
- ✅ FUNC-1: Firefox `profiles.ini` parsing (not broad `.default` matching)
- ✅ FUNC-2: Terminal scheme activated after merge
- ✅ FUNC-3: Terminal settings path searches 3 locations
- ✅ FUNC-4: `restore_defaults()` handles 10 components
- ✅ FUNC-5: Start orb uses `os.path.basename(src)`
- ✅ QOL-1: `core.logger.log` used everywhere
- ✅ QOL-3: Single `DISPATCH` dict
- ✅ QOL-4: `copy.deepcopy` in IconSetManager
- ✅ QOL-5: Windhawk reload via `subprocess.Popen`
- ✅ QOL-7: `Applier` singleton pattern available
- ✅ QOL-8: `delete_theme` uses `self.themes.pop()`
- ✅ QOL-9: Dynamic `os.environ` paths in asset_studio
- ✅ QOL-10: Terminal backup before modification
- ✅ QOL-11: `threading.Lock` as `Applier._lock`
- ✅ QOL-13: Most `.bak` files removed (see Fix 3 for the one exception)
- ✅ QOL-14: Terminal scheme merge updates existing by name
- ✅ SDK: Full `themelauncher/` package exists with 15 agents + facade + CLI
- ✅ `main.py`: Wired to `ThemeSDK` with daemon threads and graceful teardown
- ✅ `ui/app.py`: Dual-constructor (SDK or ThemeManager), safety snapshots, smart rollback
- ✅ `setup_themes.py`: DRK 25 section complete (17,150 bytes)
- ✅ `config.json`: Updated to absolute path

---

## Remaining Fixes

### Fix 1 — Cursor Role Mapping Uses Positional Index Instead of Semantic Matching [P1]

**File**: `core/applier.py`, inside `_apply_cursors()`

**Bug**: The code sorts all cursor file paths alphabetically and assigns them to Windows registry roles by positional index:

```python
role_map = {
    "Arrow": "Arrow",
    "Help": "Help",
    "AppStarting": "AppStarting",
    "Wait": "Wait",
    "Crosshair": "Crosshair",
    "IBeam": "IBeam",
    "NWPen": "NWPen",
    "No": "No",
    "SizeNS": "SizeNS",
    "SizeWE": "SizeWE",
    "SizeNWSE": "SizeNWSE",
    "SizeNESW": "SizeNESW",
    "SizeAll": "SizeAll",
    "UpArrow": "UpArrow",
    "Hand": "Hand",
}
# Map filenames to roles (best-effort)
file_list = sorted(cursor_files.values())
for i, (role, _) in enumerate(role_map.items()):
    if i < len(file_list):
        winreg.SetValueEx(key, role, 0, winreg.REG_SZ, file_list[i])
```

**What goes wrong**: If a cursor folder contains `appstarting.ani`, `arrow.cur`, `hand.cur`, the sorted list puts `appstarting.ani` first. The "Arrow" registry role (first in `role_map`) gets `appstarting.ani` instead of `arrow.cur`. The `role_map` dict values are identity strings (e.g., `"Arrow": "Arrow"`) and are never used for actual filename matching — the code ignores them entirely.

Additionally, if a cursor folder has fewer than 15 cursor files, the later registry roles are simply left unset, meaning those cursors revert to the system default mid-scheme.

**Fix**: Replace the positional loop with semantic filename-based matching. Add this constant and helper near the top of the class or at module level:

```python
# Semantic cursor role mapping: registry key → filename substrings to search for
CURSOR_ROLE_PATTERNS = {
    "Arrow": ["arrow", "normal", "select"],
    "Help": ["help", "question"],
    "AppStarting": ["appstarting", "appstart", "working"],
    "Wait": ["wait", "hourglass"],
    "Crosshair": ["crosshair", "cross", "precision"],
    "IBeam": ["ibeam", "text", "beam"],
    "NWPen": ["nwpen", "pen"],
    "No": ["no", "unavailable"],
    "SizeNS": ["sizens", "ns"],
    "SizeWE": ["sizewe", "we"],
    "SizeNWSE": ["sizenwse", "nwse"],
    "SizeNESW": ["sizenesw", "nesw"],
    "SizeAll": ["sizeall", "move"],
    "UpArrow": ["uparrow", "up"],
    "Hand": ["hand", "link", "pointer"],
}


def _match_cursor_to_role(role_name: str, filenames: list[str]) -> str | None:
    """Find the best-matching cursor file for a given Windows registry cursor role."""
    patterns = CURSOR_ROLE_PATTERNS.get(role_name, [role_name.lower()])
    for pattern in patterns:
        for fname in filenames:
            if pattern in fname.lower():
                return fname
    return None
```

Then replace the positional loop inside `_apply_cursors()` with:

```python
# Set individual cursor keys via semantic filename matching
cursor_filenames = sorted(cursor_files.keys())  # just filenames, not full paths
assigned: set[str] = set()
for role in role_map:
    matched = _match_cursor_to_role(role, cursor_filenames)
    if matched and matched not in assigned:
        winreg.SetValueEx(key, role, 0, winreg.REG_SZ, cursor_files[matched])
        assigned.add(matched)
    elif role == "Arrow":
        # Arrow is the default cursor — use first unassigned file as fallback
        for fname in cursor_filenames:
            if fname not in assigned:
                winreg.SetValueEx(key, role, 0, winreg.REG_SZ, cursor_files[fname])
                assigned.add(fname)
                break
```

**Why `Arrow` gets special treatment**: The Arrow cursor is the default/fallback cursor shown when no specific role matches. It should always be set even if no filename contains "arrow" — any cursor is better than none for this role.

---

### Fix 2 — `_luminance()` Missing sRGB Linearization (WCAG 2.1 Non-Compliant) [P1]

**File**: `themelauncher/agents/accessibility.py`, `_luminance()` method

**Bug**: The method uses raw sRGB channel values directly in the luminance formula:

```python
def _luminance(self, hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
```

**What goes wrong**: sRGB uses a gamma curve (~2.4). Raw sRGB values are perceptually compressed, not linear. The WCAG 2.1 spec (section 1.4.3) explicitly requires converting sRGB values to linear light before computing relative luminance. Without linearization, the formula underestimates luminance for mid-range colors and produces incorrect contrast ratios.

**Example**: Purple `#800080` — the simplified formula gives luminance ~0.0722, but the correct WCAG luminance is ~0.0615. This changes the contrast ratio against black from 1.76:1 (simplified) to 1.66:1 (correct). For a dark theme where `text` is `#cdd6f4` and `background` is `#1c2333`, the difference can flip a pass/fail verdict on AA compliance.

**Fix**: Replace `_luminance()` with:

```python
def _luminance(self, hex_color: str) -> float:
    """Calculate relative luminance per WCAG 2.1 (sRGB linearization required)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0

    def linearize(c: float) -> float:
        """Convert sRGB channel to linear light per WCAG 2.1 spec."""
        if c <= 0.04045:
            return c / 12.92
        else:
            return ((c + 0.055) / 1.055) ** 2.4

    r_lin = linearize(r)
    g_lin = linearize(g)
    b_lin = linearize(b)

    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin
```

**Also apply the same fix** to `themelauncher/agents/compatibility.py`, which has an inline `_luminance()` helper inside `check_visual_contrast()`. That function has the same simplified formula and should be replaced with the WCAG-compliant version.

---

### Fix 3 — `config.json.bak` Still in Working Tree [P2]

**File**: `C:\Users\kyleh\.gemini\themelauncher\config.json.bak`

The QOL-13 cleanup removed 5 `.bak` files but missed this one at the project root. It shows up in the directory listing alongside `config.json`. Delete it:

```
del config.json.bak
```

Or in Python: `os.remove(os.path.join(PROJECT_ROOT, "config.json.bak"))`

---

### Fix 4 — `suggest_fixes()` Always Hardcodes Lightness to 0.7 [P2]

**File**: `themelauncher/agents/accessibility.py`, `suggest_fixes()` method

**Bug**: The method always sets lightness to `0.7` regardless of context:

```python
def suggest_fixes(self, violations: list[dict], palette: dict) -> dict[str, str]:
    fixes = {}
    for v in violations:
        if v.get("type") == "contrast":
            fg = palette.get(v["pair"].split("/")[1])
            if fg:
                h, s, l = self._hex_to_hsl(fg)
                fixes[fg] = self._hsl_to_hex(h, s, 0.7)  # ← always 0.7
    return fixes
```

**What goes wrong**: For a dark theme where the background is `#1c2333` (lightness ~0.19) and text needs more contrast, setting the background's lightness to 0.7 would produce a bright mid-tone that destroys the entire dark theme aesthetic. The fix should darken or lighten depending on which direction improves the contrast ratio.

**Fix**: Replace with a contrast-aware adjustment that iterates toward a compliant value:

```python
def suggest_fixes(self, violations: list[dict], palette: dict) -> dict[str, str]:
    """Auto-generate corrected palette values that meet WCAG AA contrast."""
    fixes = {}
    for v in violations:
        if v.get("type") == "contrast":
            fg_key, bg_key = v["pair"].split("/")
            bg = palette.get(bg_key)
            fg = palette.get(fg_key)
            if not fg or not bg:
                continue

            # Determine which color to adjust (prefer adjusting the non-text color)
            target_hex = bg
            other_hex = fg

            # Try darkening, then lightening, pick whichever meets the ratio first
            h, s, l = self._hex_to_hsl(target_hex)

            # Try darkening
            for new_l in [l - i * 0.05 for i in range(1, 10)]:
                if new_l < 0:
                    break
                candidate = self._hsl_to_hex(h, s, max(0, new_l))
                if self._contrast_ratio(fg, candidate) >= 4.5:
                    fixes[target_hex] = candidate
                    break

            # If darkening didn't work, try lightening
            if target_hex not in fixes:
                for new_l in [l + i * 0.05 for i in range(1, 10)]:
                    if new_l > 1:
                        break
                    candidate = self._hsl_to_hex(h, s, min(1, new_l))
                    if self._contrast_ratio(fg, candidate) >= 4.5:
                        fixes[target_hex] = candidate
                        break

    return fixes
```

This preserves the original hue and saturation, only adjusting lightness in small increments until the WCAG AA ratio of 4.5:1 is met. It tries darkening first (since most themes in this project are dark), then falls back to lightening.

---

### Fix 5 — `_hex_to_hsl` / `_hsl_to_hex` Variable Naming Confusion [P2]

**File**: `themelauncher/agents/accessibility.py`

**Issue**: The methods are named "hsl" but `colorsys.rgb_to_hls` returns `(h, l, s)` — HLS order, not HSL. The code works correctly by accident because both methods use the same swapped convention:

```python
def _hex_to_hsl(self, hex_color: str) -> tuple[float, float, float]:
    ...
    return colorsys.rgb_to_hls(r, g, b)  # returns (h, L, S) but stored as (h, s, l)

def _hsl_to_hex(self, h: float, s: float, l: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, l, s)  # passes L as 2nd arg, S as 3rd — correct for HLS
    ...
```

The variable names `s` and `l` are swapped relative to what `colorsys` expects, but since both methods swap them the same way, the round-trip produces correct results. However, this is confusing for anyone maintaining the code, and it's what caused Fix 4's `0.7` bug (the developer probably thought `s` was saturation when it's actually lightness).

**Fix**: Rename to use `hls` naming consistently, or swap the variable names to match the actual return order:

```python
def _hex_to_hls(self, hex_color: str) -> tuple[float, float, float]:
    """Convert hex to HLS. Returns (hue, lightness, saturation)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0
    return colorsys.rgb_to_hls(r, g, b)  # (h, l, s)

def _hls_to_hex(self, hue: float, lightness: float, saturation: float) -> str:
    """Convert HLS to hex. Arguments: (hue, lightness, saturation)."""
    r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"
```

Then update all call sites (`suggest_fixes`, etc.) to use `h, l, s = self._hex_to_hls(...)` and `self._hls_to_hex(h, new_l, s)`. If you implement Fix 4 as written above, this rename is already accounted for.

---

### Fix 6 — `_apply_themes()` Still Uses `os.startfile()` (Same Bug as BUG-1) [P2]

**File**: `core/applier.py`, `_apply_themes()` method

**Bug**: BUG-1 fixed `_apply_msstyles()` to use registry broadcast + `SendMessageW` instead of `os.startfile()`. But the separate `_apply_themes()` method (for standalone `.theme` files in the "themes" component type) still uses `os.startfile()`:

```python
def _apply_themes(self, theme_name, component, variant_name=None):
    ...
    os.startfile(full_path)
    return {"success": True, "message": f"Applied theme file: {variant['name']}"}
```

This opens the Display Properties dialog instead of silently applying the theme — the exact same problem BUG-1 fixed for msstyles.

**Fix**: Apply the same registry broadcast pattern used in `_apply_msstyles()`:

```python
def _apply_themes(self, theme_name, component, variant_name=None):
    try:
        variant = self._get_variant(component, variant_name)
        if not variant:
            return {"success": False, "message": "No theme variant found"}

        full_path = self._resolve(theme_name, variant["file"])
        if not full_path or not os.path.exists(full_path):
            return {"success": False, "message": f"File not found: {full_path}"}

        # Apply via registry broadcast (same pattern as _apply_msstyles)
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes",
                0,
                winreg.KEY_WRITE,
            )
            winreg.SetValueEx(key, "CurrentTheme", 0, winreg.REG_SZ, full_path)
            winreg.CloseKey(key)
            ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "ImmersiveColorSet")
            log.info("Applied theme via registry broadcast: %s", full_path)
        except Exception as reg_exc:
            log.warning("Registry broadcast failed, falling back to startfile: %s", reg_exc)
            os.startfile(full_path)

        return {"success": True, "message": f"Applied theme file: {variant['name']}"}
    except Exception as exc:
        return {"success": False, "message": str(exc)}
```

---

### Fix 7 — Agent Stub Implementations [P2]

**Files**: Multiple files in `themelauncher/agents/`

Several agents have methods that return placeholder values. These are not blocking for core functionality but should be implemented over time:

**7a. `community_index.py` — `download_and_validate()`**
Returns `"Remote download not implemented"`. Needs `requests`/`urllib` to fetch remote theme packs, validate their manifests, and import them into the local themes directory.

**7b. `perf_analyzer.py` — `benchmark_baseline()` / `benchmark_after()`**
Returns placeholder metrics. Should measure UI response time, themed process memory usage, and file I/O latency before and after theme application.

**7c. `monitor.py` — `watch()`**
The real-time error polling is skeletal. Should tail the log file and invoke the callback when new ERROR/CRITICAL entries appear.

**7d. `scheduler.py` — `start()` / `stop()`**
The `main.py` entry point calls `sdk.start_scheduler()` and `sdk.stop_scheduler()`. Ensure the background thread actually evaluates cron rules and applies themes at the scheduled time, rather than just idling.

---

## Implementation Order

1. **Fix 1** — Cursor role mapping (most visible bug — wrong cursors applied)
2. **Fix 2** — WCAG luminance (correctness bug — wrong contrast reports)
3. **Fix 6** — `_apply_themes()` registry broadcast (same class of bug as BUG-1)
4. **Fix 4** — `suggest_fixes()` contrast-aware adjustment (depends on Fix 2 for correct ratios)
5. **Fix 5** — Rename `_hex_to_hsl` → `_hex_to_hls` (clean up while working on accessibility.py)
6. **Fix 3** — Delete `config.json.bak` (one-liner)
7. **Fix 7** — Agent stubs (ongoing, lowest priority)

---

## Verification Checklist

After all fixes are applied, verify:

- [ ] `_apply_cursors()` uses `_match_cursor_to_role()` — no positional index mapping
- [ ] `AccessibilityChecker._luminance('#800080')` returns approximately 0.0615 (not 0.0722)
- [ ] `compatibility.py` `check_visual_contrast()` also uses the WCAG linearized formula
- [ ] `suggest_fixes()` adjusts lightness incrementally toward 4.5:1 ratio (not hardcoded 0.7)
- [ ] `_hex_to_hsl` / `_hsl_to_hex` renamed to `_hex_to_hls` / `_hls_to_hex` with correct parameter names
- [ ] `_apply_themes()` uses registry broadcast + `SendMessageW` with fallback to `os.startfile`
- [ ] `config.json.bak` no longer exists in the project root
- [ ] All existing functionality still works (no regressions from the changes)
