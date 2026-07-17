"""Theme card for the sidebar — theme-reactive."""

import os
import tkinter as tk

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
        self.theme_path = theme_data.get("path")
        self.colors = colors
        self.on_select = on_select
        self.selected = False

        # takefocus is rejected by CTkFrame's kwarg filter, so set it on
        # the underlying tk.Frame directly via the unbound method.
        tk.Frame.configure(self, takefocus=True)

        self._build()
        self._bind_descendants()
        self._bind_keyboard()

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

    def _bind_descendants(self):
        """Recursively bind click + right-click on this card and every
        descendant widget, so clicks anywhere inside the card trigger
        selection and right-click opens the context menu."""
        widgets = [self]
        stack = list(self.winfo_children())
        while stack:
            w = stack.pop()
            widgets.append(w)
            stack.extend(w.winfo_children())
        for w in widgets:
            w.bind("<Button-1>", self._on_click, add="+")
            w.bind("<Button-3>", self._on_right_click, add="+")

    def _bind_keyboard(self):
        """Make the card keyboard-navigable (WCAG 2.1 SC 2.1.1)."""
        self.bind("<Return>", self._on_click)
        self.bind("<space>", self._on_click)
        self.bind("<FocusIn>", self._on_focus_in)
        self.bind("<FocusOut>", self._on_focus_out)

    def _on_focus_in(self, event=None):
        # Only draw the focus ring if the card isn't already selected —
        # otherwise we'd overwrite the selection accent.
        if not self.selected:
            p = self.colors.palette
            self.configure(border_color=p["active"])

    def _on_focus_out(self, event=None):
        if not self.selected:
            p = self.colors.palette
            self.configure(border_color=p["border"])

    def _on_click(self, event=None):
        self.on_select(self.theme_name)

    def _on_right_click(self, event=None):
        p = self.colors.palette
        menu = tk.Menu(self, tearoff=0,
                       bg=p["accent"], fg=p["text"],
                       activebackground=p["border"], activeforeground=p["text"],
                       borderwidth=0)
        menu.add_command(label="Apply", command=self._on_click)
        menu.add_separator()
        if self.theme_path and hasattr(os, "startfile"):
            menu.add_command(
                label="Open in File Explorer",
                command=lambda: self._open_in_explorer(),
            )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _open_in_explorer(self):
        if self.theme_path and hasattr(os, "startfile"):
            try:
                os.startfile(self.theme_path)  # type: ignore[attr-defined]
            except Exception:
                pass

    def set_selected(self, selected: bool):
        self.selected = selected
        p = self.colors.palette
        if selected:
            self.configure(fg_color=p["active"], border_color=p["accent"])
        else:
            self.configure(fg_color=p["card_fg"], border_color=p["border"])

    def update_palette(self, palette: dict[str, str]):
        """Called by App when the global palette changes."""
        if not self.winfo_exists():
            return
        if self.selected:
            self.configure(fg_color=palette["active"], border_color=palette["accent"])
        else:
            self.configure(fg_color=palette["card_fg"], border_color=palette["border"])
        self.title_label.configure(text_color=palette["text"])
        if hasattr(self, "desc_label"):
            self.desc_label.configure(text_color=palette["border"])

    def deselect(self):
        self.set_selected(False)