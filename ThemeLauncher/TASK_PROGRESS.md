# Theme Launcher - Bug Fixes & SDK Agent Implementation

## Bug Fixes from Code Review

### Critical Bugs
- [x] BUG-1: Fix rundll32/startfile theme application → Use SetSystemVisualStyle + registry broadcast
- [x] BUG-2: Cursor registry update (already fixed in current code)
- [x] BUG-3: Font elevation warning (already partially fixed, improve)
- [x] BUG-4: Double theme discovery (already fixed)
- [x] BUG-5: set_active_theme drops folder components (already fixed)
- [x] BUG-6: Mixer save_as_theme overwrites variants (already fixed)

### Functional Issues
- [x] FUNC-1: Firefox profile detection - target default-release specifically
- [x] FUNC-2: Terminal scheme activation (already fixed)
- [x] FUNC-3: Hardcoded terminal path (already fixed)
- [x] FUNC-4: Incomplete restore defaults - add terminal, firefox, windhawk cleanup
- [x] FUNC-5: Start orb hardcoded filename (already fixed)
- [x] FUNC-6: IconSlotPicker method (not present in current code)

### Quality of Life
- [x] QOL-1: Replace print() with logging (already in place via core.logger)
- [x] QOL-2: Add undo/history stack via Snapshot agent
- [x] QOL-3: Extract duplicate dispatch dict (already done as DISPATCH class attr)
- [x] QOL-4: Fix shallow copy (already fixed with deepcopy)
- [x] QOL-5: Add Windhawk reload (already implemented)
- [x] QOL-6: Strengthen manifest validation (enhance manifest_parser.py)
- [x] QOL-7: Create Applier once (add lazily-created applier to theme_manager)
- [x] QOL-8: Optimize delete_theme (already uses incremental del, no re-scan)
- [x] QOL-9: Remove hardcoded paths (already dynamic in asset_studio.py)
- [x] QOL-10: Add backup before config edits (already done for terminal)
- [x] QOL-11: Add concurrency protection (add threading.Lock to Applier)
- [x] QOL-12: Complete DRK 25 setup script
- [x] QOL-13: Clean up .bak files
- [x] QOL-14: Terminal scheme merge updates existing (already fixed)

## SDK Agent Implementation
- [x] Create agents/ directory structure
- [x] Create themelauncher/ SDK package structure
- [x] Create snapshot.py - Registry Snapshot and Smart Rollback agent
- [x] Create manifest_generator.py - Manifest Auto-Generator agent
- [x] Create compatibility.py - Compatibility and Conflict Detector agent
- [x] Create variant_generator.py - Auto-Variant Generator agent
- [x] Create update_resilience.py - Windows Update Resilience Monitor agent
- [x] Create pack_manager.py - Pack Manager agent
- [x] Create converter.py - Icon Pack Converter agent
- [x] Create monitor.py - Crash Monitor agent
- [x] Create recommender.py - Smart Theme Recommender agent
- [x] Create community_index.py - Community Theme Index agent
- [x] Create diff_engine.py - Theme Diff Engine agent
- [x] Create accessibility.py - Accessibility Compliance Checker agent
- [x] Create perf_analyzer.py - Performance Impact Analyzer agent
- [x] Create scheduler.py - Scheduled Theme Switcher agent
- [x] Create packager.py - Theme Packager and Publisher agent
- [x] Create sdk.py - ThemeSDK Facade
- [x] Create cli/main.py - CLI entry point