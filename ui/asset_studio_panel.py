"""
Asset Studio Panel — tabbed panel with Icons and Cursors tabs.
Shown when user clicks "Studio" in the sidebar.
Replaces both center and right panels.
Theme-reactive: re-colors when the active theme changes.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog
from typing import Any, Dict, List, Optional

import customtkinter as ctk
from PIL import Image, ImageDraw

try:
    from core.asset_studio import DRAW_FUNCTIONS, CursorSetManager, IconSetManager
except ImportError:
    IconSetManager = None
    CursorSetManager = None
    DRAW_FUNCTIONS: Dict[str, Any] = {}

try:
    from core.logger import log
except ImportError:
    # Fallback if core.logger is unavailable at import time.
    import logging
    log = logging.getLogger("asset_studio")

# Palette key shortcuts
_BG = "background"
_ACCENT = "accent"
_TEXT = "text"
_INACT = "card_fg"       # Use card_fg for card backgrounds
_BORDER = "border"
_ACTIVE = "active"

CURSOR_ROLES: List[str] = [
    "Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam",
    "NWPen", "No", "SizeNS", "SizeWE", "SizeNWSE", "SizeNESW",
    "SizeAll", "UpArrow", "Hand",
]

_PLACEHOLDER_SIZE = (64, 64)


def _make_placeholder(size, color):
    img = Image.new("RGBA", size, color)
    return ctk.CTkImage(light_image=img, size=size)


def _load_icon_image(path, size=(64, 64)):
    if not path or not os.path.exists(path):
        return None
    try:
        img = Image.open(path)
        img = img.resize(size, Image.LANCZOS)
        return ctk.CTkImage(light_image=img.convert("RGBA"), size=size)
    except Exception:
        return None


def _load_cursor_image(path, size=(48, 48)):
    if not path or not os.path.exists(path):
        return None
    try:
        img = Image.open(path)
        try:
            img.seek(0)
        except (AttributeError, EOFError):
            pass
        img = img.resize(size, Image.LANCZOS)
        return ctk.CTkImage(light_image=img.convert("RGBA"), size=size)
    except Exception:
        return None


def _section_header(parent, text, p):
    hdr = ctk.CTkFrame(parent, fg_color=p[_ACCENT], corner_radius=0,
                        border_color=p[_BORDER], border_width=1)
    hdr.pack(fill="x", pady=(10, 2))
    ctk.CTkLabel(hdr, text=text,
                  font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                  text_color=p[_BORDER]).pack(side="left", padx=10, pady=4)
    return hdr


def _bind_keyboard_card(widget, handler, colors):
    """Make a card-like CTkFrame keyboard-navigable.

    - Sets ``takefocus=True`` via the unbound ``tk.Frame.configure`` (CTkFrame's
      kwarg filter rejects ``takefocus=`` directly).
    - Binds ``<Return>`` and ``<space>`` to ``handler``.
    - Adds a FocusIn/FocusOut ring using ``colors.p('active')`` / ``colors.p('border')``.
    """
    tk.Frame.configure(widget, takefocus=True)
    widget.bind("<Return>", handler)
    widget.bind("<space>", handler)

    def _focus_in(_event=None):
        if not widget.winfo_exists():
            return
        try:
            widget.configure(border_color=colors.p(_ACTIVE))
        except Exception:
            pass

    def _focus_out(_event=None):
        if not widget.winfo_exists():
            return
        try:
            widget.configure(border_color=colors.p(_BORDER))
        except Exception:
            pass

    widget.bind("<FocusIn>", _focus_in, add="+")
    widget.bind("<FocusOut>", _focus_out, add="+")


class AssetStudioPanel(ctk.CTkFrame):
    """Outer container with tab bar for Icons and Cursors. Theme-reactive."""

    def __init__(self, parent, icon_manager, cursor_manager, colors, theme_manager,
                 on_error=None):
        p = colors.palette
        super().__init__(parent, corner_radius=0, fg_color=p[_BG])
        self._icon_manager = icon_manager
        self._cursor_manager = cursor_manager
        self._colors = colors
        self._theme_manager = theme_manager
        self._active_tab = "icons"
        self._on_error = on_error

        self._build()
        self._colors.register(self._on_palette_change)

    def destroy(self):
        """Unregister the palette callback before tearing down."""
        try:
            self._colors.unregister(self._on_palette_change)
        except Exception:
            pass
        super().destroy()

    def _notify_error(self, message: str) -> None:
        """Route an error to the App's status bar (if wired)."""
        if callable(self._on_error):
            try:
                self._on_error(message)
            except Exception:
                pass

    def _on_palette_change(self, palette: dict[str, str]):
        if not self.winfo_exists():
            return
        self.configure(fg_color=palette[_BG])
        self._tab_bar.configure(fg_color=palette[_ACCENT], border_color=palette[_BORDER])
        self._content_frame.configure(fg_color="transparent")
        # Update tab button colors
        p = palette
        if self._active_tab == "icons":
            self._icons_tab_btn.configure(fg_color=p[_ACTIVE], text_color=p[_BG])
            self._cursors_tab_btn.configure(fg_color=p[_INACT], text_color=p[_TEXT])
        else:
            self._cursors_tab_btn.configure(fg_color=p[_ACTIVE], text_color=p[_BG])
            self._icons_tab_btn.configure(fg_color=p[_INACT], text_color=p[_TEXT])
        # Sub-frames will pick up new palette on next rebuild

    def _build(self):
        p = self._colors.palette

        # Tab bar
        self._tab_bar = ctk.CTkFrame(self, fg_color=p[_ACCENT], corner_radius=0,
                                      border_color=p[_BORDER], border_width=1)
        self._tab_bar.pack(fill="x")

        self._icons_tab_btn = ctk.CTkButton(
            self._tab_bar, text="Icons",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=p[_ACTIVE], text_color=p[_BG],
            hover_color=p[_BORDER], corner_radius=0,
            command=lambda: self._switch_tab("icons"),
        )
        self._icons_tab_btn.pack(side="left", padx=(12, 2), pady=8)

        self._cursors_tab_btn = ctk.CTkButton(
            self._tab_bar, text="Cursors",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=p[_INACT], text_color=p[_TEXT],
            hover_color=p[_BORDER], corner_radius=0,
            command=lambda: self._switch_tab("cursors"),
        )
        self._cursors_tab_btn.pack(side="left", padx=(2, 12), pady=8)

        # Content area
        self._content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._content_frame.pack(fill="both", expand=True)

        # Icon studio
        self._icon_studio = _IconStudioFrame(
            self._content_frame, self._icon_manager, self._colors, self._theme_manager,
            on_error=self._notify_error,
        )
        self._icon_studio.pack(fill="both", expand=True)

        # Cursor studio (hidden initially)
        self._cursor_studio = _CursorStudioFrame(
            self._content_frame, self._cursor_manager, self._colors, self._theme_manager,
            on_error=self._notify_error,
        )

    def _switch_tab(self, tab):
        p = self._colors.palette
        self._active_tab = tab

        if tab == "icons":
            self._cursor_studio.pack_forget()
            self._icon_studio.pack(fill="both", expand=True)
            self._icons_tab_btn.configure(fg_color=p[_ACTIVE], text_color=p[_BG],
                                          font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"))
            self._cursors_tab_btn.configure(fg_color=p[_INACT], text_color=p[_TEXT],
                                            font=ctk.CTkFont(family="Segoe UI", size=11))
        else:
            self._icon_studio.pack_forget()
            self._cursor_studio.pack(fill="both", expand=True)
            self._cursors_tab_btn.configure(fg_color=p[_ACTIVE], text_color=p[_BG],
                                            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"))
            self._icons_tab_btn.configure(fg_color=p[_INACT], text_color=p[_TEXT],
                                          font=ctk.CTkFont(family="Segoe UI", size=11))


class _SaveSetDialog(ctk.CTkToplevel):
    def __init__(self, parent, p, callback):
        super().__init__(parent)
        self.title("Save as New Set")
        self.geometry("320x150")
        self.configure(fg_color=p[_BG])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self._cb = callback
        # Stash the palette so validation can use the theme's error colour
        # rather than a hardcoded literal.
        self._palette = p

        ctk.CTkLabel(self, text="New Set Name",
                      font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                      text_color=p[_TEXT]).pack(padx=16, pady=(16, 4), anchor="w")

        self._entry = ctk.CTkEntry(self, corner_radius=0, fg_color=p[_ACCENT],
                                    text_color=p[_TEXT], border_color=p[_BORDER])
        self._entry.pack(fill="x", padx=16, pady=(0, 12))
        self._entry.focus()

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack()
        ctk.CTkButton(row, text="Cancel", corner_radius=0,
                       fg_color=p[_ACCENT], text_color=p[_TEXT],
                       hover_color=p[_BORDER], command=self.destroy).pack(side="left", padx=6)
        ctk.CTkButton(row, text="Save", corner_radius=0,
                       fg_color=p[_TEXT], text_color=p[_ACTIVE],
                       hover_color=p[_BORDER], command=self._save).pack(side="left", padx=6)

    def _save(self):
        name = self._entry.get().strip()
        if not name:
            # Use the theme's error colour rather than a hardcoded literal.
            self._entry.configure(border_color=self._palette["error"])
            return
        self.destroy()
        self._cb(name)


class _IconStudioFrame(ctk.CTkFrame):
    """Three-column icon set editor. Theme-reactive."""

    def __init__(self, parent, icon_manager, colors, theme_manager, on_error=None):
        p = colors.palette
        super().__init__(parent, corner_radius=0, fg_color=p[_BG])
        self._icon_manager = icon_manager
        self._colors = colors
        self._theme_manager = theme_manager
        self._on_error = on_error
        self._selected_set: Optional[str] = None
        self._current_mix: Dict[str, str] = {}
        self._selected_app: Optional[str] = None
        self._image_refs: List[ctk.CTkImage] = []
        self._set_row_widgets: Dict[str, ctk.CTkFrame] = {}
        # Initialise the recolour hex field from the active palette so it
        # reflects the current theme instead of a hardcoded orange.
        self._hex_var = tk.StringVar(value=colors.p(_ACCENT))

        self._build_columns()
        self._load_set_list()
        self._colors.register(self._on_palette_change)

    def destroy(self):
        """Unregister the palette callback before tearing down."""
        try:
            self._colors.unregister(self._on_palette_change)
        except Exception:
            pass
        super().destroy()

    def _notify_error(self, message: str) -> None:
        if callable(self._on_error):
            try:
                self._on_error(message)
            except Exception:
                pass

    def _on_palette_change(self, palette: dict[str, str]):
        if not self.winfo_exists():
            return
        self.configure(fg_color=palette[_BG])
        # Rebuild columns with new palette
        self._left.configure(fg_color=palette[_INACT], border_color=palette[_BORDER])
        self._center.configure(fg_color=palette[_BG], border_color=palette[_BORDER])
        self._right.configure(fg_color=palette[_INACT], border_color=palette[_BORDER])
        # Rebuild set list and slot grid with new colors
        self._load_set_list()
        if self._selected_set:
            self._select_set(self._selected_set)

    def _build_columns(self):
        p = self._colors.palette
        self.grid_columnconfigure(0, minsize=220, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, minsize=260, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # Left — set list
        self._left = ctk.CTkFrame(self, corner_radius=0, fg_color=p[_INACT],
                                   border_color=p[_BORDER], border_width=1, width=220)
        self._left.grid(row=0, column=0, sticky="nsew")
        self._left.pack_propagate(False)

        ctk.CTkLabel(self._left, text="ICON SETS",
                      font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                      text_color=p[_TEXT]).pack(padx=12, pady=(12, 6), anchor="w")

        self._set_scroll = ctk.CTkScrollableFrame(self._left, fg_color="transparent",
                                                    scrollbar_button_color=p[_BORDER],
                                                    scrollbar_button_hover_color=p[_TEXT])
        self._set_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        ctk.CTkButton(self._left, text="+ New Set", corner_radius=0,
                       fg_color=p[_ACCENT], text_color=p[_TEXT],
                       hover_color=p[_BORDER], border_color=p[_BORDER], border_width=1,
                       font=ctk.CTkFont(family="Segoe UI", size=10),
                       command=self._new_set).pack(fill="x", padx=8, pady=(0, 8))

        # Center — slot grid
        self._center = ctk.CTkFrame(self, corner_radius=0, fg_color=p[_BG],
                                     border_color=p[_BORDER], border_width=1)
        self._center.grid(row=0, column=1, sticky="nsew")
        self._center.grid_rowconfigure(1, weight=1)
        self._center.grid_columnconfigure(0, weight=1)

        center_header = ctk.CTkFrame(self._center, corner_radius=0, fg_color=p[_ACCENT],
                                      border_color=p[_BORDER], border_width=1)
        center_header.grid(row=0, column=0, sticky="ew")
        self._center_set_label = ctk.CTkLabel(
            center_header, text="— select a set —",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=p[_TEXT])
        self._center_set_label.pack(side="left", padx=16, pady=10)

        self._slot_scroll = ctk.CTkScrollableFrame(self._center, fg_color=p[_BG],
                                                     scrollbar_button_color=p[_BORDER],
                                                     scrollbar_button_hover_color=p[_TEXT])
        self._slot_scroll.grid(row=1, column=0, sticky="nsew")

        ctk.CTkLabel(self._slot_scroll, text="Select an icon set\nto edit its slots.",
                      font=ctk.CTkFont(family="Segoe UI", size=12),
                      text_color=p[_BORDER]).pack(expand=True, pady=40)

        # Center footer
        center_footer = ctk.CTkFrame(self._center, corner_radius=0, fg_color=p[_ACCENT],
                                      border_color=p[_BORDER], border_width=1)
        center_footer.grid(row=2, column=0, sticky="ew")
        ctk.CTkButton(center_footer, text="Apply Set", corner_radius=0,
                       fg_color=p[_TEXT], text_color=p[_ACTIVE],
                       hover_color=p[_BORDER],
                       font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                       command=self._apply_set).pack(fill="x", padx=12, pady=8)

        # Right — controls
        self._right = ctk.CTkFrame(self, corner_radius=0, fg_color=p[_INACT],
                                    border_color=p[_BORDER], border_width=1, width=260)
        self._right.grid(row=0, column=2, sticky="nsew")
        self._right.pack_propagate(False)
        self._build_right_controls()

    def _build_right_controls(self):
        for w in self._right.winfo_children():
            w.destroy()

        p = self._colors.palette
        scroll = ctk.CTkScrollableFrame(self._right, fg_color="transparent",
                                         scrollbar_button_color=p[_BORDER],
                                         scrollbar_button_hover_color=p[_TEXT])
        scroll.pack(fill="both", expand=True)

        _section_header(scroll, "RECOLOUR", p)
        ctk.CTkLabel(scroll, text="Colour",
                      font=ctk.CTkFont(family="Segoe UI", size=9),
                      text_color=p[_BORDER]).pack(anchor="w", padx=10, pady=(4, 1))
        ctk.CTkEntry(scroll, corner_radius=0, textvariable=self._hex_var,
                      fg_color=p[_ACCENT], text_color=p[_TEXT],
                      border_color=p[_BORDER]).pack(fill="x", padx=10, pady=(0, 6))

        # Palette swatches
        swatch_row = ctk.CTkFrame(scroll, fg_color="transparent")
        swatch_row.pack(fill="x", padx=10, pady=(0, 8))
        for pk in [_BG, _ACCENT, _TEXT, _INACT, _BORDER, _ACTIVE]:
            color = p.get(pk, "#888888")
            def _make_cmd(c):
                def _cmd():
                    self._hex_var.set(c)
                return _cmd
            ctk.CTkButton(swatch_row, text="", width=28, height=18, corner_radius=0,
                           fg_color=color, hover_color=color,
                           border_color=p[_BORDER], border_width=1,
                           command=_make_cmd(color)).pack(side="left", padx=2)

        for label, cmd in [
            ("Recolour Selected Slot", self._recolour_slot),
            ("Recolour Whole Set", self._recolour_set),
            ("Save as New Set", self._save_as_new_set),
        ]:
            ctk.CTkButton(scroll, text=label, corner_radius=0,
                           fg_color=p[_INACT], text_color=p[_TEXT],
                           hover_color=p[_BORDER], border_color=p[_BORDER], border_width=1,
                           font=ctk.CTkFont(family="Segoe UI", size=10),
                           command=cmd).pack(fill="x", padx=10, pady=2)

        _section_header(scroll, "CAPTION BUTTONS", p)
        ctk.CTkLabel(scroll, text="Extract & tint from .msstyles",
                      font=ctk.CTkFont(family="Segoe UI", size=9),
                      text_color=p[_BORDER]).pack(anchor="w", padx=10, pady=(4, 4))
        
        ctk.CTkButton(scroll, text="Extract & Recolour", corner_radius=0,
                       fg_color=p[_INACT], text_color=p[_TEXT],
                       hover_color=p[_BORDER], border_color=p[_BORDER], border_width=1,
                       font=ctk.CTkFont(family="Segoe UI", size=10),
                       command=self._extract_msstyles_buttons).pack(fill="x", padx=10, pady=2)

    def _extract_msstyles_buttons(self):
        file_path = filedialog.askopenfilename(
            title="Select .msstyles",
            filetypes=[("MSStyles", "*.msstyles")]
        )
        if not file_path:
            return
        
        hex_val = self._hex_var.get().strip()
        if not hex_val or self._icon_manager is None:
            return
            
        try:
            out_dir = filedialog.askdirectory(title="Select Output Directory for Images")
            if not out_dir:
                return
            
            results = self._icon_manager.recolour_msstyles_buttons(file_path, hex_val, out_dir)
            if results:
                print(f"[AssetStudio] Extracted {len(results)} buttons to {out_dir}")
            else:
                print(f"[AssetStudio] No buttons found in {file_path}")
        except Exception as exc:
            print(f"[AssetStudio] extract error: {exc}")

    def _load_set_list(self):
        for w in self._set_scroll.winfo_children():
            w.destroy()
        self._set_row_widgets.clear()
        sets = []
        if self._icon_manager is not None:
            try:
                sets = self._icon_manager.get_sets()
            except Exception as exc:
                log.warning("[AssetStudio] icon get_sets failed: %s", exc)
                self._notify_error(f"Icon sets could not be loaded: {exc}")
        p = self._colors.palette
        for set_name in sets:
            row = ctk.CTkFrame(self._set_scroll, corner_radius=0,
                               fg_color=p[_ACCENT], border_color=p[_BORDER], border_width=1)
            row.pack(fill="x", padx=4, pady=2)
            lbl = ctk.CTkLabel(row, text=set_name,
                               font=ctk.CTkFont(family="Segoe UI", size=10),
                               text_color=p[_TEXT], anchor="w")
            lbl.pack(side="left", padx=10, pady=8, fill="x", expand=True)
            self._set_row_widgets[set_name] = row

            def _make_handler(sn):
                def _handler(e=None):
                    self._select_set(sn)
                return _handler
            h = _make_handler(set_name)
            row.bind("<Button-1>", h)
            lbl.bind("<Button-1>", h)
            # Keyboard navigation for the row.
            _bind_keyboard_card(row, h, self._colors)
            _bind_keyboard_card(lbl, h, self._colors)

        if not sets:
            ctk.CTkLabel(self._set_scroll, text="No icon sets found.",
                          font=ctk.CTkFont(family="Segoe UI", size=10),
                          text_color=p[_BORDER]).pack(pady=20)

    def _select_set(self, set_name):
        p = self._colors.palette
        for sn, row in self._set_row_widgets.items():
            row.configure(fg_color=p[_ACTIVE] if sn == set_name else p[_ACCENT])
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    child.configure(text_color=p[_BG] if sn == set_name else p[_TEXT])
        self._selected_set = set_name
        self._center_set_label.configure(text=set_name)
        self._current_mix = {}
        if self._icon_manager is not None:
            try:
                self._current_mix = dict(self._icon_manager.get_set_contents(set_name))
            except Exception:
                pass
        self._rebuild_slot_grid()

    def _rebuild_slot_grid(self):
        for w in self._slot_scroll.winfo_children():
            w.destroy()
        self._image_refs = []

        p = self._colors.palette

        if self._selected_set is None:
            ctk.CTkLabel(self._slot_scroll, text="Select an icon set\nto edit its slots.",
                          font=ctk.CTkFont(family="Segoe UI", size=12),
                          text_color=p[_BORDER]).pack(expand=True, pady=40)
            return

        apps = []
        if self._icon_manager is not None:
            try:
                apps = self._icon_manager.get_apps()
            except Exception:
                pass

        grid = ctk.CTkFrame(self._slot_scroll, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=10, pady=10)

        COLS = 4
        for col in range(COLS):
            grid.grid_columnconfigure(col, weight=1, uniform="islot")

        for i, app in enumerate(apps):
            app_key = app.get("key", app) if isinstance(app, dict) else str(app)
            app_label = app.get("label", app_key) if isinstance(app, dict) else app_key

            ico_file = self._current_mix.get(app_key, "")
            icon_path = ""
            if ico_file and self._icon_manager is not None:
                icon_path = self._icon_manager.resolve_icon_path(self._selected_set, app_key, ico_file)

            img = _load_icon_image(icon_path, (64, 64))
            if img is None:
                img = _make_placeholder((64, 64), p[_ACCENT])
            self._image_refs.append(img)

            row_i = i // COLS
            col_i = i % COLS

            card = ctk.CTkFrame(grid, corner_radius=0, fg_color=p[_INACT],
                                 border_color=p[_BORDER], border_width=1)
            card.grid(row=row_i, column=col_i, padx=4, pady=4, sticky="nsew")

            icon_lbl = ctk.CTkLabel(card, image=img, text="", width=64, height=64, fg_color=p[_ACCENT])
            icon_lbl.pack(padx=6, pady=(6, 2))

            ctk.CTkLabel(card, text=app_label,
                          font=ctk.CTkFont(family="Segoe UI", size=10),
                          text_color=p[_TEXT], wraplength=80, justify="center").pack()

            ctk.CTkLabel(card, text=f"from: {self._selected_set}",
                          font=ctk.CTkFont(family="Segoe UI", size=10),
                          text_color=p[_BORDER], wraplength=80, justify="center").pack(pady=(0, 4))

            def _make_click(ak, al):
                def _click(e=None):
                    self._selected_app = ak
                return _click
            click_handler = _make_click(app_key, app_label)
            card.bind("<Button-1>", click_handler)
            icon_lbl.bind("<Button-1>", click_handler)

    def _recolour_slot(self):
        if not self._selected_app or not self._selected_set:
            return
        hex_val = self._hex_var.get().strip()
        if not hex_val or self._icon_manager is None:
            return
        try:
            self._icon_manager.recolour_slot(self._selected_set, self._selected_app, hex_val)
            self._rebuild_slot_grid()
        except Exception as exc:
            log.warning("[AssetStudio] recolour_slot error: %s", exc)
            self._notify_error(f"Recolour slot failed: {exc}")

    def _recolour_set(self):
        if not self._selected_set:
            return
        hex_val = self._hex_var.get().strip()
        if not hex_val or self._icon_manager is None:
            return
        try:
            self._icon_manager.recolour_set(self._selected_set, hex_val)
            self._rebuild_slot_grid()
        except Exception as exc:
            log.warning("[AssetStudio] recolour_set error: %s", exc)
            self._notify_error(f"Recolour set failed: {exc}")

    def _save_as_new_set(self):
        def _do_save(name):
            if self._icon_manager is not None:
                try:
                    self._icon_manager.save_mixed_as_set(name, self._current_mix)
                    self._load_set_list()
                    self._select_set(name)
                except Exception as exc:
                    log.warning("[AssetStudio] save error: %s", exc)
                    self._notify_error(f"Save icon set failed: {exc}")
        _SaveSetDialog(self, self._colors.palette, _do_save)

    def _apply_set(self):
        if not self._selected_set or self._icon_manager is None:
            return
        try:
            self._icon_manager.apply_mixed(self._current_mix)
        except Exception as exc:
            log.warning("[AssetStudio] apply error: %s", exc)
            self._notify_error(f"Apply icon set failed: {exc}")

    def _new_set(self):
        def _do_create(name):
            if self._icon_manager is not None:
                try:
                    self._icon_manager.create_set(name)
                    self._load_set_list()
                    self._select_set(name)
                except Exception as exc:
                    log.warning("[AssetStudio] new_set error: %s", exc)
                    self._notify_error(f"Create icon set failed: {exc}")
        _SaveSetDialog(self, self._colors.palette, _do_create)


class _CursorStudioFrame(ctk.CTkFrame):
    """Three-column cursor set editor. Theme-reactive."""

    def __init__(self, parent, cursor_manager, colors, theme_manager, on_error=None):
        p = colors.palette
        super().__init__(parent, corner_radius=0, fg_color=p[_BG])
        self._cursor_manager = cursor_manager
        self._colors = colors
        self._theme_manager = theme_manager
        self._on_error = on_error
        self._selected_set: Optional[str] = None
        self._current_cursor_mix: Dict[str, str] = {}
        self._selected_role: Optional[str] = None
        self._image_refs: List[ctk.CTkImage] = []
        self._set_row_widgets: Dict[str, ctk.CTkFrame] = {}
        # Initialise from the active palette (was hardcoded "#D58C40").
        self._hex_var = tk.StringVar(value=colors.p(_ACCENT))

        self._build_columns()
        self._load_set_list()
        self._colors.register(self._on_palette_change)

    def destroy(self):
        """Unregister the palette callback before tearing down."""
        try:
            self._colors.unregister(self._on_palette_change)
        except Exception:
            pass
        super().destroy()

    def _notify_error(self, message: str) -> None:
        if callable(self._on_error):
            try:
                self._on_error(message)
            except Exception:
                pass

    def _on_palette_change(self, palette: dict[str, str]):
        if not self.winfo_exists():
            return
        self.configure(fg_color=palette[_BG])
        self._left.configure(fg_color=palette[_INACT], border_color=palette[_BORDER])
        self._center.configure(fg_color=palette[_BG], border_color=palette[_BORDER])
        self._right.configure(fg_color=palette[_INACT], border_color=palette[_BORDER])
        self._load_set_list()
        if self._selected_set:
            self._select_set(self._selected_set)

    def _build_columns(self):
        p = self._colors.palette
        self.grid_columnconfigure(0, minsize=220, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, minsize=260, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # Left — set list
        self._left = ctk.CTkFrame(self, corner_radius=0, fg_color=p[_INACT],
                                   border_color=p[_BORDER], border_width=1, width=220)
        self._left.grid(row=0, column=0, sticky="nsew")
        self._left.pack_propagate(False)

        ctk.CTkLabel(self._left, text="CURSOR SETS",
                      font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                      text_color=p[_TEXT]).pack(padx=12, pady=(12, 6), anchor="w")

        self._set_scroll = ctk.CTkScrollableFrame(self._left, fg_color="transparent",
                                                    scrollbar_button_color=p[_BORDER],
                                                    scrollbar_button_hover_color=p[_TEXT])
        self._set_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # Center — role grid
        self._center = ctk.CTkFrame(self, corner_radius=0, fg_color=p[_BG],
                                     border_color=p[_BORDER], border_width=1)
        self._center.grid(row=0, column=1, sticky="nsew")
        self._center.grid_rowconfigure(1, weight=1)
        self._center.grid_columnconfigure(0, weight=1)

        center_header = ctk.CTkFrame(self._center, corner_radius=0, fg_color=p[_ACCENT],
                                      border_color=p[_BORDER], border_width=1)
        center_header.grid(row=0, column=0, sticky="ew")
        self._center_set_label = ctk.CTkLabel(
            center_header, text="— select a set —",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=p[_TEXT])
        self._center_set_label.pack(side="left", padx=16, pady=10)

        self._slot_scroll = ctk.CTkScrollableFrame(self._center, fg_color=p[_BG],
                                                     scrollbar_button_color=p[_BORDER],
                                                     scrollbar_button_hover_color=p[_TEXT])
        self._slot_scroll.grid(row=1, column=0, sticky="nsew")

        ctk.CTkLabel(self._slot_scroll, text="Select a cursor set\nto preview its roles.",
                      font=ctk.CTkFont(family="Segoe UI", size=12),
                      text_color=p[_BORDER]).pack(expand=True, pady=40)

        # Center footer
        center_footer = ctk.CTkFrame(self._center, corner_radius=0, fg_color=p[_ACCENT],
                                      border_color=p[_BORDER], border_width=1)
        center_footer.grid(row=2, column=0, sticky="ew")
        ctk.CTkButton(center_footer, text="Apply Cursor Set", corner_radius=0,
                       fg_color=p[_TEXT], text_color=p[_ACTIVE],
                       hover_color=p[_BORDER],
                       font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                       command=self._apply_set).pack(fill="x", padx=12, pady=8)

        # Right — controls
        self._right = ctk.CTkFrame(self, corner_radius=0, fg_color=p[_INACT],
                                    border_color=p[_BORDER], border_width=1, width=260)
        self._right.grid(row=0, column=2, sticky="nsew")
        self._right.pack_propagate(False)
        self._build_right_controls()

    def _build_right_controls(self):
        for w in self._right.winfo_children():
            w.destroy()

        p = self._colors.palette
        scroll = ctk.CTkScrollableFrame(self._right, fg_color="transparent",
                                         scrollbar_button_color=p[_BORDER],
                                         scrollbar_button_hover_color=p[_TEXT])
        scroll.pack(fill="both", expand=True)

        _section_header(scroll, "RECOLOUR", p)
        ctk.CTkLabel(scroll, text="Colour",
                      font=ctk.CTkFont(family="Segoe UI", size=9),
                      text_color=p[_BORDER]).pack(anchor="w", padx=10, pady=(4, 1))
        ctk.CTkEntry(scroll, corner_radius=0, textvariable=self._hex_var,
                      fg_color=p[_ACCENT], text_color=p[_TEXT],
                      border_color=p[_BORDER]).pack(fill="x", padx=10, pady=(0, 6))

        swatch_row = ctk.CTkFrame(scroll, fg_color="transparent")
        swatch_row.pack(fill="x", padx=10, pady=(0, 8))
        for pk in [_BG, _ACCENT, _TEXT, _INACT, _BORDER, _ACTIVE]:
            color = p.get(pk, "#888888")
            def _make_cmd(c):
                def _cmd():
                    self._hex_var.set(c)
                return _cmd
            ctk.CTkButton(swatch_row, text="", width=28, height=18, corner_radius=0,
                           fg_color=color, hover_color=color,
                           border_color=p[_BORDER], border_width=1,
                           command=_make_cmd(color)).pack(side="left", padx=2)

        ctk.CTkButton(scroll, text="Recolour Whole Set", corner_radius=0,
                       fg_color=p[_INACT], text_color=p[_TEXT],
                       hover_color=p[_BORDER], border_color=p[_BORDER], border_width=1,
                       font=ctk.CTkFont(family="Segoe UI", size=10),
                       command=self._recolour_set).pack(fill="x", padx=10, pady=2)

        ctk.CTkButton(scroll, text="Save as New Set", corner_radius=0,
                       fg_color=p[_INACT], text_color=p[_TEXT],
                       hover_color=p[_BORDER], border_color=p[_BORDER], border_width=1,
                       font=ctk.CTkFont(family="Segoe UI", size=10),
                       command=self._save_as_new_set).pack(fill="x", padx=10, pady=2)

    def _load_set_list(self):
        for w in self._set_scroll.winfo_children():
            w.destroy()
        self._set_row_widgets.clear()
        sets = {}
        if self._cursor_manager is not None:
            try:
                sets = self._cursor_manager.get_all_sets()
            except Exception as exc:
                log.warning("[CursorStudio] get_all_sets failed: %s", exc)
                self._notify_error(f"Cursor sets could not be loaded: {exc}")
        p = self._colors.palette
        for set_name in sets:
            row = ctk.CTkFrame(self._set_scroll, corner_radius=0,
                               fg_color=p[_ACCENT], border_color=p[_BORDER], border_width=1)
            row.pack(fill="x", padx=4, pady=2)
            lbl = ctk.CTkLabel(row, text=set_name,
                               font=ctk.CTkFont(family="Segoe UI", size=10),
                               text_color=p[_TEXT], anchor="w")
            lbl.pack(side="left", padx=10, pady=8, fill="x", expand=True)
            self._set_row_widgets[set_name] = row

            def _make_handler(sn):
                def _handler(e=None):
                    self._select_set(sn)
                return _handler
            h = _make_handler(set_name)
            row.bind("<Button-1>", h)
            lbl.bind("<Button-1>", h)
            # Keyboard navigation for the row.
            _bind_keyboard_card(row, h, self._colors)
            _bind_keyboard_card(lbl, h, self._colors)

        if not sets:
            ctk.CTkLabel(self._set_scroll, text="No cursor sets found.",
                          font=ctk.CTkFont(family="Segoe UI", size=10),
                          text_color=p[_BORDER]).pack(pady=20)

    def _select_set(self, set_name):
        p = self._colors.palette
        for sn, row in self._set_row_widgets.items():
            row.configure(fg_color=p[_ACTIVE] if sn == set_name else p[_ACCENT])
            for child in row.winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    child.configure(text_color=p[_BG] if sn == set_name else p[_TEXT])
        self._selected_set = set_name
        self._center_set_label.configure(text=set_name)

        # Load the cursor role map
        self._current_cursor_mix = {}
        if self._cursor_manager is not None:
            try:
                all_sets = self._cursor_manager.get_all_sets()
                self._current_cursor_mix = all_sets.get(set_name, {})
            except Exception:
                pass
        self._rebuild_role_grid()

    def _rebuild_role_grid(self):
        for w in self._slot_scroll.winfo_children():
            w.destroy()
        self._image_refs = []

        p = self._colors.palette

        if self._selected_set is None or not self._current_cursor_mix:
            ctk.CTkLabel(self._slot_scroll, text="Select a cursor set\nto preview its roles.",
                          font=ctk.CTkFont(family="Segoe UI", size=12),
                          text_color=p[_BORDER]).pack(expand=True, pady=40)
            return

        grid = ctk.CTkFrame(self._slot_scroll, fg_color="transparent")
        grid.pack(fill="both", expand=True, padx=10, pady=10)

        COLS = 5
        for col in range(COLS):
            grid.grid_columnconfigure(col, weight=1, uniform="cslot")

        for i, (role, path) in enumerate(self._current_cursor_mix.items()):
            img = _load_cursor_image(path, (48, 48))
            if img is None:
                img = _make_placeholder((48, 48), p[_ACCENT])
            self._image_refs.append(img)

            row_i = i // COLS
            col_i = i % COLS

            card = ctk.CTkFrame(grid, corner_radius=0, fg_color=p[_INACT],
                                 border_color=p[_BORDER], border_width=1)
            card.grid(row=row_i, column=col_i, padx=4, pady=4, sticky="nsew")

            ctk.CTkLabel(card, image=img, text="", width=48, height=48, fg_color=p[_ACCENT]).pack(padx=4, pady=(4, 2))
            ctk.CTkLabel(card, text=role,
                          font=ctk.CTkFont(family="Segoe UI", size=9, weight="bold"),
                          text_color=p[_TEXT], wraplength=72, justify="center").pack()
            ctk.CTkLabel(card, text=os.path.splitext(os.path.basename(path))[0],
                          font=ctk.CTkFont(family="Segoe UI", size=10),
                          text_color=p[_BORDER], wraplength=72, justify="center").pack(pady=(0, 4))

            def _make_click(r, p):
                def _click(e=None):
                    self._selected_role = r
                return _click
            click_handler = _make_click(role, path)
            card.bind("<Button-1>", click_handler)

    def _recolour_set(self):
        if not self._selected_set or self._cursor_manager is None:
            return
        hex_val = self._hex_var.get().strip()
        if not hex_val:
            return
        try:
            new_name = f"{self._selected_set} (recoloured)"
            self._cursor_manager.recolour_set(self._selected_set, new_name, hex_val)
            self._load_set_list()
            self._select_set(new_name)
        except Exception as exc:
            log.warning("[CursorStudio] recolour error: %s", exc)
            self._notify_error(f"Recolour cursor set failed: {exc}")

    def _save_as_new_set(self):
        def _do_save(name):
            if self._cursor_manager is not None:
                try:
                    self._cursor_manager.save_mix(name, self._current_cursor_mix)
                    self._load_set_list()
                    self._select_set(f"Custom: {name}")
                except Exception as exc:
                    log.warning("[CursorStudio] save error: %s", exc)
                    self._notify_error(f"Save cursor set failed: {exc}")
        _SaveSetDialog(self, self._colors.palette, _do_save)

    def _apply_set(self):
        if not self._selected_set or self._cursor_manager is None:
            return
        try:
            self._cursor_manager.apply_set(self._current_cursor_mix)
        except Exception as exc:
            log.warning("[CursorStudio] apply error: %s", exc)
            self._notify_error(f"Apply cursor set failed: {exc}")