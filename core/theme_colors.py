"""
Theme-aware color manager for the GUI.

Centralises palette state so every panel updates when the active theme changes.
Panels register callbacks; when the palette updates, all callbacks fire and
every widget re-colors itself.

Palette keys (defined in manifest_parser.REQUIRED_PALETTE_KEYS):
    background, accent, text, inactive, border, active

Extended keys (auto-derived if missing from manifest):
    card_fg       — card/item background  (falls back to inactive)
    card_hover    — card hover color      (falls back to border)
    danger        — destructive action bg (falls back to #8B2E2E)
    danger_hover  — destructive hover     (falls back to #A33A3A)
    success       — success indicator     (falls back to #4CAF50)
    error         — error indicator       (falls back to #C42B1C)
    status_fg     — status bar text       (falls back to border)
"""

from __future__ import annotations

import colorsys
from typing import Callable

from core.logger import log

# ── Palette keys every manifest MUST provide ──
REQUIRED_KEYS = ("background", "accent", "text", "inactive", "border", "active")

# ── Extended keys derived automatically ──
_EXTENDED_DEFAULTS = {
    "card_fg":      ("inactive",),
    "card_hover":   ("border",),
    "danger":       (),
    "danger_hover": (),
    "success":      (),
    "error":        (),
    "status_fg":    ("border",),
}

# Hardcoded fallbacks for extended keys (when no manifest key chains to them)
_HARDCODED_FALLBACKS = {
    "danger":       "#8B2E2E",
    "danger_hover": "#A33A3A",
    "success":      "#4CAF50",
    "error":        "#C42B1C",
}

_DEFAULT_PALETTE: dict[str, str] = {
    "background":   "#2b2b2b",
    "accent":       "#3d3d3d",
    "text":         "#ffffff",
    "inactive":     "#1a1a1a",
    "border":       "#555555",
    "active":       "#ffffff",
    "card_fg":      "#1a1a1a",
    "card_hover":   "#555555",
    "danger":       "#8B2E2E",
    "danger_hover": "#A33A3A",
    "success":      "#4CAF50",
    "error":        "#C42B1C",
    "status_fg":    "#555555",
}


def _resolve_palette(raw: dict[str, str]) -> dict[str, str]:
    """Take a manifest palette (may be missing extended keys) and return a
    fully-populated palette with all required + extended keys."""
    out: dict[str, str] = {}

    # 1. Required keys — fill from raw, falling back to defaults
    for key in REQUIRED_KEYS:
        out[key] = raw.get(key, _DEFAULT_PALETTE[key])

    # 2. Extended keys — follow chain, then hardcode
    for ext_key, chain in _EXTENDED_DEFAULTS.items():
        if ext_key in raw and raw[ext_key]:
            out[ext_key] = raw[ext_key]
        else:
            # Walk the chain (e.g. card_fg -> inactive)
            resolved = None
            for chain_key in chain:
                if chain_key in out:
                    resolved = out[chain_key]
                    break
            if resolved:
                out[ext_key] = resolved
            else:
                out[ext_key] = _HARDCODED_FALLBACKS.get(ext_key, _DEFAULT_PALETTE.get(ext_key, "#444444"))

    # 3. Auto-derive danger colors from accent if they're still the hardcoded fallback
    #    but the accent is very different — adjust danger to be a darker/red-shifted
    #    version of accent for better theme cohesion.
    try:
        accent_hex = out["accent"].lstrip("#")
        r, g, b = (int(accent_hex[i:i+2], 16) / 255.0 for i in (0, 2, 4))
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        # Shift hue toward red (0.0) and boost saturation for danger
        danger_h = (h * 0.3) % 1.0  # Bias toward red
        danger_s = min(1.0, s + 0.2)
        danger_v = max(0.35, v - 0.1)
        dr, dg, db = colorsys.hsv_to_rgb(danger_h, danger_s, danger_v)
        out["danger"] = f"#{int(dr*255):02x}{int(dg*255):02x}{int(db*255):02x}"
        # Hover is slightly brighter
        dh_r, dh_g, dh_b = colorsys.hsv_to_rgb(danger_h, danger_s, min(1.0, danger_v + 0.08))
        out["danger_hover"] = f"#{int(dh_r*255):02x}{int(dh_g*255):02x}{int(dh_b*255):02x}"
    except Exception:
        pass  # Keep defaults if color math fails

    return out


class ThemeColors:
    """Singleton-style colour manager.

    Panels call ``register(callback)`` to be notified of palette changes.
    The App calls ``update_palette(raw)`` whenever the active theme changes.
    """

    def __init__(self, raw_palette: dict[str, str] | None = None):
        self._callbacks: list[Callable[[dict[str, str]], None]] = []
        if raw_palette:
            self._palette = _resolve_palette(raw_palette)
        else:
            self._palette = dict(_DEFAULT_PALETTE)

    # ── Public API ──

    @property
    def palette(self) -> dict[str, str]:
        """Read-only snapshot of the current palette."""
        return dict(self._palette)

    def p(self, key: str) -> str:
        """Shorthand: ``colors.p("accent")`` — returns the hex color string."""
        return self._palette.get(key, _DEFAULT_PALETTE.get(key, "#444444"))

    def update_palette(self, raw_palette: dict[str, str]) -> None:
        """Resolve and broadcast a new palette. All registered callbacks fire."""
        new = _resolve_palette(raw_palette)
        if new == self._palette:
            return  # No change — skip repaint
        self._palette = new
        log.info("ThemeColors: palette updated — broadcasting to %d listener(s)", len(self._callbacks))
        for cb in self._callbacks:
            try:
                cb(self._palette)
            except Exception:
                log.exception("ThemeColors: callback error during palette update")

    def register(self, callback: Callable[[dict[str, str]], None]) -> None:
        """Register a callback that receives the full palette dict on change."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def unregister(self, callback: Callable[[dict[str, str]], None]) -> None:
        """Remove a previously registered callback."""
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    def reset_to_default(self) -> None:
        """Revert to the built-in dark palette."""
        self.update_palette(dict(_DEFAULT_PALETTE))