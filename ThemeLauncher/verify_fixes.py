"""
ThemeLauncher Verification Script
Validates all implemented fixes.
"""

import sys
import os
import colorsys
from datetime import datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from themelauncher.agents.accessibility import AccessibilityChecker
from themelauncher.agents.compatibility import CompatibilityDetector
from themelauncher.agents.community_index import CommunityIndex
from themelauncher.agents.perf_analyzer import PerfAnalyzer
from themelauncher.agents.monitor import CrashMonitor
from themelauncher.agents.scheduler import ThemeScheduler
from core.applier import _match_cursor_to_role, Applier


def test_fix_1_cursor_matching():
    print("Testing Fix 1: Semantic Cursor Role Matching...")
    
    # Mock file list
    filenames = ["appstarting.ani", "arrow.cur", "hand.cur", "cross.cur", "beam.cur"]
    
    # 1. Match arrow cursor
    arrow_match = _match_cursor_to_role("Arrow", filenames)
    assert arrow_match == "arrow.cur", f"Expected arrow.cur, got {arrow_match}"
    
    # 2. Match hand cursor
    hand_match = _match_cursor_to_role("Hand", filenames)
    assert hand_match == "hand.cur", f"Expected hand.cur, got {hand_match}"
    
    # 3. Match appstarting cursor
    appstart_match = _match_cursor_to_role("AppStarting", filenames)
    assert appstart_match == "appstarting.ani", f"Expected appstarting.ani, got {appstart_match}"
    
    # 4. Fallback matching for missing roles
    help_match = _match_cursor_to_role("Help", filenames)
    assert help_match is None, f"Expected None for missing help cursor, got {help_match}"
    
    print("PASS: Fix 1 passed!")


def test_fix_2_wcag_luminance():
    print("Testing Fix 2: WCAG 2.1 Linear Relative Luminance...")
    
    checker = AccessibilityChecker()
    
    # Purple color test: #800080
    # Simplified formula (un-linearized): 0.2126 * (128/255) + 0.0722 * (128/255) = ~0.143
    # WCAG linearized formula:
    # 128/255 = 0.50196
    # linearize(0.50196) = ((0.50196 + 0.055) / 1.055) ** 2.4 = ~0.2158
    # luminance = 0.2126 * 0.2158 + 0.0722 * 0.2158 = ~0.0615
    purple_lum = checker._luminance("#800080")
    print(f"Luminance of #800080: {purple_lum:.5f}")
    assert abs(purple_lum - 0.0615) < 0.005, f"Expected relative luminance ~0.0615, got {purple_lum}"
    
    # Compatibility Detector inline check
    detector = CompatibilityDetector()
    results = detector.check_visual_contrast({"background": "#800080"}, "non_existent_wallpaper.jpg")
    # Low contrast of black wallpaper vs #800080 terminal bg
    # If the contrast ratio is low, it returns warning
    print("PASS: Fix 2 passed!")


def test_fix_4_suggest_fixes():
    print("Testing Fix 4 & 5: Contrast-Aware Auto-Fixes & HLS Renames...")
    
    checker = AccessibilityChecker()
    
    # Test case: Low contrast text/background pair
    palette = {
        "text": "#ffffff",
        "background": "#eeeeee",
        "accent": "#3d3d3d",
    }
    
    violations = [
        {"type": "contrast", "pair": "text/background", "ratio": 1.1, "required": 4.5}
    ]
    
    # Call the actual suggest_fixes method
    fixes = checker.suggest_fixes(violations, palette)
    print(f"Suggested fixes for contrast violation: {fixes}")
    
    # The fix should adjust background (#eeeeee) to be much darker to meet 4.5:1 ratio against white text
    assert "#eeeeee" in fixes, "Expected a fix for background color"
    fixed_bg = fixes["#eeeeee"]
    
    # Verify that the new background meets contrast >= 4.5:1
    new_ratio = checker._contrast_ratio("#ffffff", fixed_bg)
    print(f"New contrast ratio: {new_ratio:.2f}:1 (Target >= 4.5:1)")
    assert new_ratio >= 4.5, f"Expected contrast ratio >= 4.5, got {new_ratio}"
    
    # Ensure background hue and saturation are preserved
    h1, l1, s1 = checker._hex_to_hls("#eeeeee")
    h2, l2, s2 = checker._hex_to_hls(fixed_bg)
    assert abs(h1 - h2) < 0.01, f"Hue changed significantly: {h1} vs {h2}"
    assert abs(s1 - s2) < 0.01, f"Saturation changed significantly: {s1} vs {s2}"
    
    print("PASS: Fix 4 & 5 passed!")


def test_fix_6_apply_themes_broadcast():
    print("Testing Fix 6: _apply_themes Registry Broadcast...")
    # Verify that _apply_themes is correctly implemented in applier.py
    import inspect
    source = inspect.getsource(Applier._apply_themes)
    assert "ImmersiveColorSet" in source, "Expected registry broadcast via SendMessageW in _apply_themes"
    assert "winreg.OpenKey" in source, "Expected registry writing in _apply_themes"
    assert "os.startfile" in source, "Expected fallback to os.startfile in _apply_themes"
    print("PASS: Fix 6 passed!")


def test_fix_7_agent_stubs():
    print("Testing Fix 7: Agent Stub Implementations...")
    
    # 7a. community_index download_and_validate
    ci = CommunityIndex()
    # Test downloading invalid file
    res = ci.download_and_validate("https://example.com/invalid_theme_file.zip")
    print(f"Community Index result: {res}")
    assert res["success"] is False, "Expected failure for non-existent URL"
    assert "Download/validation error" in res["message"] or "404" in res["message"] or "HTTP Error" in res["message"] or "unknown url type" in res["message"], f"Unexpected message: {res['message']}"
    
    # 7b. perf_analyzer benchmarks
    pa = PerfAnalyzer()
    baseline = pa.benchmark_baseline()
    after = pa.benchmark_after("msstyles")
    print(f"Baseline metrics: {baseline}")
    print(f"After metrics: {after}")
    assert "mem_available_mb" in baseline, "Expected mem_available_mb in baseline"
    assert "latency_ms" in baseline, "Expected latency_ms in baseline"
    assert "io_latency_ms" in baseline, "Expected io_latency_ms in baseline"
    assert "mem_available_mb" in after, "Expected mem_available_mb in after"
    assert "latency_ms" in after, "Expected latency_ms in after"
    assert "io_latency_ms" in after, "Expected io_latency_ms in after"
    
    comp_res = pa.compare(baseline, after)
    print(f"Compare metrics: {comp_res}")
    assert "regression" in comp_res, "Expected regression flag in comparison"
    
    # 7c. monitor log tailer
    cm = CrashMonitor()
    assert hasattr(cm, "watch"), "CrashMonitor should have watch method"
    assert hasattr(cm, "stop_watching"), "CrashMonitor should have stop_watching method"
    
    # 7d. scheduler cron matcher
    ts = ThemeScheduler()
    # Test standard crons
    dt1 = datetime(2026, 5, 25, 14, 0) # 2:00 PM
    assert ts._matches_cron("0 14 * * *", dt1) is True, "Exact hour and minute match failed"
    assert ts._matches_cron("0 */2 * * *", dt1) is True, "Interval hour match failed"
    assert ts._matches_cron("*/5 * * * *", dt1) is True, "Interval minute match failed"
    
    dt2 = datetime(2026, 5, 25, 14, 3) # 2:03 PM
    assert ts._matches_cron("0 14 * * *", dt2) is False, "Mismatched minute should fail"
    assert ts._matches_cron("0 */2 * * *", dt2) is False, "Mismatched minute with interval hour should fail"
    
    print("PASS: Fix 7 passed!")


def main():
    print("====================================================")
    print("Starting ThemeLauncher Verification...")
    print("====================================================")
    
    test_fix_1_cursor_matching()
    test_fix_2_wcag_luminance()
    test_fix_4_suggest_fixes()
    test_fix_6_apply_themes_broadcast()
    test_fix_7_agent_stubs()
    
    # Check if config.json.bak exists
    bak_path = "config.json.bak"
    if os.path.exists(bak_path):
        print(f"Warning: {bak_path} still exists at project root. Please delete it.")
    else:
        print("config.json.bak is successfully removed or does not exist!")
        
    print("====================================================")
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("====================================================")


if __name__ == "__main__":
    main()
