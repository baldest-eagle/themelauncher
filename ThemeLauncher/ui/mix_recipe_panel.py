"""Mix recipe panel — right side in mixer mode. Theme-reactive."""

import customtkinter as ctk


class MixRecipePanel(ctk.CTkFrame):
    def __init__(self, parent, mixer, colors, on_apply_mix, on_save_mix):
        p = colors.palette
        super().__init__(parent, corner_radius=0, fg_color=p["inactive"])
        self.mixer = mixer
        self.colors = colors
        self.on_apply_mix = on_apply_mix
        self.on_save_mix = on_save_mix
        self._build()
        self.colors.register(self._on_palette_change)

    # ------------------------------------------------------------------
    # Palette change
    # ------------------------------------------------------------------

    def _on_palette_change(self, palette: dict[str, str]):
        self.configure(fg_color=palette["inactive"])
        self._header.configure(fg_color=palette["accent"], border_color=palette["border"])
        self._header_label.configure(text_color=palette["text"])
        self._footer.configure(fg_color=palette["accent"], border_color=palette["border"])
        self._apply_btn.configure(
            fg_color=palette["background"], text_color=palette["text"],
            hover_color=palette["border"], border_color=palette["border"],
        )
        self._save_btn.configure(
            fg_color=palette["text"], text_color=palette["active"],
            hover_color=palette["border"],
        )
        self.refresh()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        p = self.colors.palette

        # Header
        self._header = ctk.CTkFrame(self, fg_color=p["accent"], corner_radius=0,
                                     border_color=p["border"], border_width=1)
        self._header.pack(fill="x")

        self._header_label = ctk.CTkLabel(
            self._header, text="MIX RECIPE",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=p["text"],
        )
        self._header_label.pack(side="left", padx=16, pady=12)

        ctk.CTkButton(
            self._header, text="X Clear", width=60, height=24,
            fg_color="transparent", text_color=p["border"],
            hover_color=p["background"], corner_radius=0,
            font=ctk.CTkFont(family="Segoe UI", size=9),
            command=self._clear_all,
        ).pack(side="right", padx=8)

        # Scrollable recipe list
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=p["border"],
            scrollbar_button_hover_color=p["text"],
        )
        self.scroll.pack(fill="both", expand=True, padx=8, pady=8)

        self.empty_label = ctk.CTkLabel(
            self.scroll, text="No components selected.\nBrowse the mixer\nto build your recipe.",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=p["border"], justify="center",
        )
        self.empty_label.pack(expand=True, pady=40)

        # Footer
        self._footer = ctk.CTkFrame(self, fg_color=p["accent"], corner_radius=0,
                                     border_color=p["border"], border_width=1)
        self._footer.pack(fill="x", side="bottom")

        self._apply_btn = ctk.CTkButton(
            self._footer, text="Apply Mix",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=p["background"], text_color=p["text"],
            hover_color=p["border"], corner_radius=0,
            border_color=p["border"], border_width=1,
            command=self._on_apply,
        )
        self._apply_btn.pack(fill="x", padx=8, pady=(8, 4))

        self._save_btn = ctk.CTkButton(
            self._footer, text="Save as New Theme",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=p["text"], text_color=p["active"],
            hover_color=p["border"], corner_radius=0,
            command=self._on_save,
        )
        self._save_btn.pack(fill="x", padx=8, pady=(4, 8))

    def refresh(self):
        p = self.colors.palette
        for w in self.scroll.winfo_children():
            w.destroy()

        mix = self.mixer.mix
        if not mix:
            ctk.CTkLabel(
                self.scroll, text="No components selected.\nBrowse the mixer\nto build your recipe.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=p["border"], justify="center",
            ).pack(expand=True, pady=40)
            return

        comp_labels = {
            "msstyles": "Visual Style", "wallpapers": "Wallpaper",
            "cursors": "Cursors", "startorb": "Start Orb",
            "themes": "Theme File", "terminal": "Terminal",
            "firefox": "Firefox", "windhawk": "Windhawk",
            "fonts": "Fonts", "icons": "Icons",
        }

        for comp_type, selection in mix.items():
            row = ctk.CTkFrame(
                self.scroll, fg_color=p["background"], corner_radius=0,
                border_color=p["border"], border_width=1,
            )
            row.pack(fill="x", pady=2)

            def make_remove(ct):
                def remove():
                    self.mixer.clear_slot(ct)
                    self.refresh()
                return remove

            ctk.CTkButton(
                row, text="X", width=20, height=20,
                fg_color="transparent", text_color=p["border"],
                hover_color=p["accent"], corner_radius=0,
                font=ctk.CTkFont(size=10),
                command=make_remove(comp_type),
            ).pack(side="right", padx=(4, 6), pady=6)

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=(8, 0), pady=6)

            label = comp_labels.get(comp_type, comp_type.capitalize())
            ctk.CTkLabel(
                left, text=label,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color=p["text"], anchor="w",
            ).pack(anchor="w")

            source = selection["theme"]
            variant = selection.get("variant")
            detail = f"{source}  >  {variant}" if variant else source
            ctk.CTkLabel(
                left, text=detail,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color=p["border"], anchor="w", wraplength=200,
            ).pack(anchor="w")

    def _clear_all(self):
        self.mixer.clear_all()
        self.refresh()

    def _on_apply(self):
        self.on_apply_mix()

    def _on_save(self):
        p = self.colors.palette

        dialog = ctk.CTkToplevel(self)
        dialog.title("Save Mix as Theme")
        dialog.geometry("380x260")
        dialog.configure(fg_color=p["background"])
        dialog.grab_set()
        dialog.resizable(False, False)

        ctk.CTkLabel(
            dialog, text="Save Mix as New Theme",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=p["text"],
        ).pack(padx=20, pady=(20, 8), anchor="w")

        ctk.CTkLabel(dialog, text="Name *",
                      font=ctk.CTkFont(family="Segoe UI", size=10),
                      text_color=p["border"]).pack(padx=20, anchor="w")
        name_entry = ctk.CTkEntry(dialog, corner_radius=0, fg_color=p["accent"],
                                   text_color=p["text"], border_color=p["border"])
        name_entry.pack(fill="x", padx=20, pady=(2, 8))

        ctk.CTkLabel(dialog, text="Description",
                      font=ctk.CTkFont(family="Segoe UI", size=10),
                      text_color=p["border"]).pack(padx=20, anchor="w")
        desc_entry = ctk.CTkEntry(dialog, corner_radius=0, fg_color=p["accent"],
                                   text_color=p["text"], border_color=p["border"])
        desc_entry.pack(fill="x", padx=20, pady=(2, 8))

        ctk.CTkLabel(dialog, text="Author",
                      font=ctk.CTkFont(family="Segoe UI", size=10),
                      text_color=p["border"]).pack(padx=20, anchor="w")
        author_entry = ctk.CTkEntry(dialog, corner_radius=0, fg_color=p["accent"],
                                     text_color=p["text"], border_color=p["border"])
        author_entry.pack(fill="x", padx=20, pady=(2, 12))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=(0, 16))

        ctk.CTkButton(
            btn_row, text="Cancel", corner_radius=0,
            fg_color=p["accent"], text_color=p["text"],
            hover_color=p["border"], command=dialog.destroy,
        ).pack(side="left", padx=8)

        def do_save():
            name = name_entry.get().strip()
            if not name:
                name_entry.configure(border_color=p["error"])
                return
            dialog.destroy()
            self.on_save_mix(name, desc_entry.get().strip(), author_entry.get().strip())

        ctk.CTkButton(
            btn_row, text="Save", corner_radius=0,
            fg_color=p["text"], text_color=p["active"],
            hover_color=p["border"], command=do_save,
        ).pack(side="left", padx=8)
