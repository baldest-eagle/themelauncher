"""Theme card for the sidebar — theme-reactive."""

import os

import customtkinter as ctk
from PIL import Image


class ThemeCard(ctk.CTkFrame):
    def __init__(self, parent, theme_name, theme_data, colors, on_select):
        p = colors.palette
        super().__init__(
            parent, corner_radius=0,
            fg_color=p["card_fg"], border_color=p["border"], border_width=1,
        )

        self.theme_name = theme_name
        self.theme_data = theme_data
        self.colors = colors
        self.on_select = on_select
        self.selected = False

        self._build()
        self._bind_clicks()

    def _build(self):
        p = self.colors.palette
        manifest = self.theme_data["manifest"]

        # Thumbnail
        self.thumb_label = ctk.CTkLabel(self, text="", width=48, height=48)
        self.thumb_label.pack(side="left", padx=(8, 6), pady=8)
        self._load_thumbnail(manifest)

        # Title
        self.title_label = ctk.CTkLabel(
            self, text=manifest["name"],
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=p["text"], anchor="w",
        )
        self.title_label.pack(side="top", fill="x", padx=(0, 8), pady=(8, 0))

        desc = manifest.get("description", "")
        if desc:
            self.desc_label = ctk.CTkLabel(
                self, text=desc[:40] + "..." if len(desc) > 40 else desc,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=p["border"], anchor="w",
            )
            self.desc_label.pack(side="top", fill="x", padx=(0, 8), pady=(0, 8))

    def _load_thumbnail(self, manifest):
        try:
            theme_dir = self.theme_data["path"]
            preview_path = manifest.get("preview")
            if preview_path:
                full_path = os.path.join(theme_dir, preview_path)
                if os.path.exists(full_path):
                    img = Image.open(full_path)
                    img = img.resize((48, 48), Image.LANCZOS)
                    ctk_img = ctk.CTkImage(light_image=img, size=(48, 48))
                    self.thumb_label.configure(image=ctk_img)
                    self.thumb_label.image = ctk_img
                    return
        except Exception:
            pass
        self.thumb_label.configure(
            fg_color=self.colors.p("accent"),
            text=self.theme_name[0].upper(),
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=self.colors.p("text"),
        )

    def _bind_clicks(self):
        self.bind("<Button-1>", self._on_click)
        for widget in self.winfo_children():
            widget.bind("<Button-1>", self._on_click)
            for child in widget.winfo_children():
                child.bind("<Button-1>", self._on_click)

    def _on_click(self, event=None):
        self.on_select(self.theme_name)

    def set_selected(self, selected: bool):
        self.selected = selected
        p = self.colors.palette
        if selected:
            self.configure(fg_color=p["active"], border_color=p["accent"])
        else:
            self.configure(fg_color=p["card_fg"], border_color=p["border"])

    def update_palette(self, palette: dict[str, str]):
        """Called by App when the global palette changes."""
        if self.selected:
            self.configure(fg_color=palette["active"], border_color=palette["accent"])
        else:
            self.configure(fg_color=palette["card_fg"], border_color=palette["border"])
        self.title_label.configure(text_color=palette["text"])
        if hasattr(self, "desc_label"):
            self.desc_label.configure(text_color=palette["border"])

    def deselect(self):
        self.set_selected(False)
