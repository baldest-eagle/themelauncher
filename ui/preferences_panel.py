"""
Windows Preferences Panel — Settings for dark mode, accent color, and wallpaper options.
"""

import customtkinter as ctk

from core.windows_prefs import WindowsPrefs


class PreferencesPanel(ctk.CTkToplevel):
    def __init__(self, parent, colors):
        super().__init__(parent)
        self.colors = colors
        self.p = colors.palette
        self.title("Windows Preferences")
        self.geometry("380x420")
        self.configure(fg_color=self.p["background"])
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._build()

    def _build(self):
        p = self.colors.palette

        dark_frame = ctk.CTkFrame(self, fg_color="transparent")
        dark_frame.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            dark_frame, text="Dark Mode",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=p["text"],
        ).pack(anchor="w")

        self.dark_var = ctk.BooleanVar(value=WindowsPrefs.get_dark_mode())
        ctk.CTkSwitch(
            dark_frame, text="Enable Dark Mode",
            variable=self.dark_var, onvalue=True, offvalue=False,
            progress_color=p["accent"],
            command=self._on_dark_toggle,
        ).pack(anchor="w", pady=(8, 0))

        accent_frame = ctk.CTkFrame(self, fg_color="transparent")
        accent_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            accent_frame, text="Accent Color",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=p["text"],
        ).pack(anchor="w")

        self.accent_entry = ctk.CTkEntry(
            accent_frame, placeholder_text="#0078d4",
            font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.accent_entry.pack(fill="x", pady=(8, 0))
        self.accent_entry.insert(0, WindowsPrefs.get_accent_color())

        preset_frame = ctk.CTkFrame(self, fg_color="transparent")
        preset_frame.pack(fill="x", padx=20, pady=(10, 0))

        presets = ["#0078d4", "#e74c3c", "#2ecc71", "#f39c12", "#9b59b6", "#1abc9c"]
        for color in presets:
            btn = ctk.CTkButton(
                preset_frame, text=" ", width=24, height=24,
                fg_color=color, hover_color=color,
                corner_radius=4,
                command=lambda c=color: self.accent_entry.delete(0, "end") or self.accent_entry.insert(0, c),
            )
            btn.pack(side="left", padx=2)

        ctk.CTkButton(
            accent_frame, text="Apply Accent",
            fg_color=p["accent"], text_color=p["text"],
            hover_color=p["border"], corner_radius=0,
            command=self._on_accent_apply,
        ).pack(anchor="e", pady=(8, 0))

        wp_frame = ctk.CTkFrame(self, fg_color="transparent")
        wp_frame.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(
            wp_frame, text="Wallpaper Style",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=p["text"],
        ).pack(anchor="w")

        self.style_var = ctk.StringVar(value="fill")
        style_combo = ctk.CTkComboBox(
            wp_frame, values=["fill", "fit", "stretch", "tile", "span"],
            variable=self.style_var,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        style_combo.pack(fill="x", pady=(8, 0))

        self.slideshow_var = ctk.BooleanVar()
        ctk.CTkCheckBox(
            wp_frame, text="Slideshow mode",
            variable=self.slideshow_var,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=p["text"],
        ).pack(anchor="w", pady=(12, 0))

        self.interval_var = ctk.IntVar(value=5)
        self.interval_spin = ctk.CTkComboBox(
            wp_frame, values=["1", "3", "5", "10", "30"],
            variable=self.interval_var,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=12),
        )
        self.interval_spin.pack(fill="x", pady=(4, 0))
        self.interval_spin.configure(state="disabled")

        ctk.CTkButton(
            self, text="Close",
            fg_color=p["accent"], text_color=p["text"],
            hover_color=p["border"], corner_radius=0,
            command=self.destroy,
        ).pack(pady=20)

        self.selected_images: list[str] = []

    def _on_dark_toggle(self):
        WindowsPrefs.set_dark_mode(self.dark_var.get())

    def _on_accent_apply(self):
        color = self.accent_entry.get().strip()
        if color.startswith("#") and len(color) == 7:
            WindowsPrefs.set_accent_color(color)

    def _on_slideshow_toggle(self):
        enabled = self.slideshow_var.get()
        self.interval_spin.configure(state="normal" if enabled else "disabled")

    def set_selected_images(self, images: list[str]):
        self.selected_images = images