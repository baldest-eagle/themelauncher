"""Mixer panel — center panel in mixer mode. Theme-reactive."""

import os

import customtkinter as ctk
from PIL import Image


class MixerPanel(ctk.CTkFrame):
    def __init__(self, parent, mixer, colors, on_slot_change):
        p = colors.palette
        super().__init__(parent, corner_radius=0, fg_color=p["background"])
        self.mixer = mixer
        self.colors = colors
        self.on_slot_change = on_slot_change
        self._image_refs = {}
        self.slot_cards = {}
        self._build()
        self.colors.register(self._on_palette_change)

    # ------------------------------------------------------------------
    # Palette change
    # ------------------------------------------------------------------

    def _on_palette_change(self, palette: dict[str, str]):
        self.configure(fg_color=palette["background"])
        self._header.configure(fg_color=palette["accent"], border_color=palette["border"])
        self._header_title.configure(text_color=palette["text"])
        self._header_sub.configure(text_color=palette["border"])
        self.scroll.configure(
            fg_color=palette["background"],
            scrollbar_button_color=palette["border"],
            scrollbar_button_hover_color=palette["text"],
        )
        # Rebuild catalog to pick up new palette
        if self.slot_cards:
            self.load_catalog()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        p = self.colors.palette

        self._header = ctk.CTkFrame(self, fg_color=p["accent"], corner_radius=0,
                                     border_color=p["border"], border_width=1)
        self._header.pack(fill="x")

        self._header_title = ctk.CTkLabel(
            self._header, text="THEME MIXER",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=p["text"],
        )
        self._header_title.pack(side="left", padx=16, pady=12)

        self._header_sub = ctk.CTkLabel(
            self._header, text="pick one per slot from any theme",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=p["border"],
        )
        self._header_sub.pack(side="left", padx=4, pady=12)

        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=p["background"],
            scrollbar_button_color=p["border"],
            scrollbar_button_hover_color=p["text"],
        )
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def load_catalog(self):
        for w in self.scroll.winfo_children():
            w.destroy()
        self.slot_cards = {}
        self._image_refs = {}

        catalog = self.mixer.get_catalog()
        p = self.colors.palette

        display_order = [
            "msstyles", "wallpapers", "cursors", "startorb", "themes",
            "terminal", "firefox", "windhawk", "fonts", "icons",
        ]
        comp_labels = {
            "msstyles": "VISUAL STYLE", "wallpapers": "WALLPAPER",
            "cursors": "CURSORS", "startorb": "START ORB",
            "themes": "THEME FILE", "terminal": "TERMINAL",
            "firefox": "FIREFOX CSS", "windhawk": "WINDHAWK",
            "fonts": "FONTS", "icons": "ICONS",
        }

        all_types = list(dict.fromkeys(
            display_order + sorted(k for k in catalog if k not in display_order)
        ))

        for comp_type in all_types:
            if comp_type not in catalog:
                continue
            entries = catalog[comp_type]
            if not entries:
                continue
            label = comp_labels.get(comp_type, comp_type.upper())
            self._build_section(comp_type, label, entries)

    def _build_section(self, comp_type, label, entries):
        p = self.colors.palette

        hdr = ctk.CTkFrame(self.scroll, fg_color=p["accent"], corner_radius=0)
        hdr.pack(fill="x", pady=(16, 4))
        ctk.CTkLabel(
            hdr, text=label,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=p["text"],
        ).pack(side="left", padx=10, pady=6)
        ctk.CTkLabel(
            hdr, text=f"{len(entries)} options",
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=p["border"],
        ).pack(side="right", padx=10, pady=6)

        grid = ctk.CTkFrame(self.scroll, fg_color="transparent")
        grid.pack(fill="x", pady=(0, 4))
        for col in range(4):
            grid.grid_columnconfigure(col, weight=1, uniform="mixcol")

        self.slot_cards[comp_type] = []
        self._image_refs[comp_type] = []

        for i, entry in enumerate(entries):
            row_idx = i // 4
            col_idx = i % 4
            card = self._build_card(grid, comp_type, entry, row_idx, col_idx)
            self.slot_cards[comp_type].append({
                "theme": entry["theme"],
                "variant": entry.get("variant"),
                "frame": card,
            })

        self._refresh_highlights(comp_type)

    def _build_card(self, grid, comp_type, entry, row_idx, col_idx):
        p = self.colors.palette
        theme_name = entry["theme"]
        variant_name = entry.get("variant")
        preview_path = entry.get("preview")

        card = ctk.CTkFrame(
            grid, fg_color=p["card_fg"], corner_radius=0,
            border_color=p["border"], border_width=1,
        )
        card.grid(row=row_idx, column=col_idx, padx=3, pady=3, sticky="nsew")

        thumb = self._load_thumb(preview_path, comp_type)
        if thumb:
            self._image_refs[comp_type].append(thumb)

        img_lbl = ctk.CTkLabel(
            card, image=thumb if thumb else None,
            text="" if thumb else "...", width=120, height=80,
            fg_color=p["accent"], font=ctk.CTkFont(size=20),
            text_color=p["border"],
        )
        img_lbl.pack(padx=3, pady=(3, 0))

        ctk.CTkLabel(
            card, text=theme_name,
            font=ctk.CTkFont(family="Segoe UI", size=8),
            text_color=p["border"], wraplength=115, justify="center",
        ).pack(padx=3, pady=(2, 0))

        display = variant_name if variant_name else "Default"
        ctk.CTkLabel(
            card, text=display,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=p["text"], wraplength=115, justify="center",
        ).pack(padx=3, pady=(0, 4))

        def make_handler(ct, tn, vn, c):
            def handler(event=None):
                self._select_card(ct, tn, vn, c)
            return handler

        h = make_handler(comp_type, theme_name, variant_name, card)
        for widget in [card, img_lbl]:
            widget.bind("<Button-1>", h)
        for child in card.winfo_children():
            child.bind("<Button-1>", h)

        return card

    def _load_thumb(self, preview_path, comp_type):
        if not preview_path or not os.path.exists(preview_path):
            return None
        try:
            img = Image.open(preview_path)
            img = img.resize((120, 80), Image.LANCZOS)
            return ctk.CTkImage(light_image=img, size=(120, 80))
        except Exception:
            return None

    def _select_card(self, comp_type, theme_name, variant_name, selected_frame):
        self.mixer.set_slot(comp_type, theme_name, variant_name)
        self._refresh_highlights(comp_type)
        self.on_slot_change(comp_type, theme_name, variant_name)

    def _refresh_highlights(self, comp_type):
        p = self.colors.palette
        slot = self.mixer.get_slot(comp_type)
        for card_info in self.slot_cards.get(comp_type, []):
            selected = (
                slot is not None
                and card_info["theme"] == slot["theme"]
                and card_info["variant"] == slot.get("variant")
            )
            if selected:
                card_info["frame"].configure(fg_color=p["active"], border_color=p["accent"])
            else:
                card_info["frame"].configure(fg_color=p["card_fg"], border_color=p["border"])
