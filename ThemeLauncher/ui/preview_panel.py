"""Preview panel — center panel in preset mode. Theme-reactive."""

import os

import customtkinter as ctk
from PIL import Image


class PreviewPanel(ctk.CTkFrame):
    def __init__(self, parent, theme_manager, colors, on_component_change):
        p = colors.palette
        super().__init__(parent, corner_radius=0, fg_color=p["background"])
        self.theme_manager = theme_manager
        self.colors = colors
        self.on_component_change = on_component_change
        self.current_theme = None
        self.variant_buttons = {}
        self._image_refs = {}
        self._build()
        self.colors.register(self._on_palette_change)

    # ------------------------------------------------------------------
    # Palette change
    # ------------------------------------------------------------------

    def _on_palette_change(self, palette: dict[str, str]):
        self.configure(fg_color=palette["background"])
        self._header.configure(fg_color=palette["accent"], border_color=palette["border"])
        self.title_label.configure(text_color=palette["text"])
        self.author_label.configure(text_color=palette["border"])
        self.preview_frame.configure(fg_color=palette["inactive"], border_color=palette["border"])
        self.scroll.configure(
            fg_color=palette["background"],
            scrollbar_button_color=palette["border"],
            scrollbar_button_hover_color=palette["text"],
        )
        # Rebuild content to pick up new palette colors
        if self.current_theme:
            self.load_theme(self.current_theme)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self):
        p = self.colors.palette

        # Header
        self._header = ctk.CTkFrame(self, fg_color=p["accent"], corner_radius=0,
                                     border_color=p["border"], border_width=1)
        self._header.pack(fill="x")

        self.title_label = ctk.CTkLabel(
            self._header, text="Select a theme",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=p["text"],
        )
        self.title_label.pack(side="left", padx=16, pady=12)

        self.author_label = ctk.CTkLabel(
            self._header, text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=p["border"],
        )
        self.author_label.pack(side="left", padx=4, pady=12)

        # Main preview image
        self.preview_frame = ctk.CTkFrame(
            self, fg_color=p["inactive"], corner_radius=0,
            border_color=p["border"], border_width=1,
        )
        self.preview_frame.pack(fill="x", padx=16, pady=16)

        self.preview_label = ctk.CTkLabel(
            self.preview_frame, text="No preview available",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=p["border"], height=200,
        )
        self.preview_label.pack(fill="x", padx=8, pady=8)

        # Scrollable content
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=p["background"],
            scrollbar_button_color=p["border"],
            scrollbar_button_hover_color=p["text"],
        )
        self.scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    def load_theme(self, theme_name: str):
        self.current_theme = theme_name
        theme = self.theme_manager.get_theme(theme_name)
        if not theme:
            return

        manifest = theme["manifest"]
        p = self.colors.palette
        self.title_label.configure(text=manifest["name"])
        author = manifest.get("author", "")
        self.author_label.configure(text=f"by {author}" if author else "")

        self._load_preview_image(theme)

        for widget in self.scroll.winfo_children():
            widget.destroy()
        self.variant_buttons = {}
        self._image_refs = {}

        components = manifest.get("components", {})
        visual_components = ["msstyles", "wallpapers"]
        for comp_name in visual_components:
            if comp_name in components:
                self._build_variant_section(comp_name, components[comp_name], theme)

        if "cursors" in components:
            self._build_cursor_section("cursors", components["cursors"], theme)

        excluded = set(visual_components) | {"cursors"}
        other_components = [c for c in components if c not in excluded]
        if other_components:
            self._build_other_section(other_components, components, theme)

    def _load_preview_image(self, theme):
        try:
            preview_path = theme["manifest"].get("preview")
            if preview_path:
                full_path = os.path.join(theme["path"], preview_path)
                if os.path.exists(full_path):
                    img = Image.open(full_path)
                    w, h = img.size
                    ratio = w / h
                    new_h = 200
                    new_w = int(new_h * ratio)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    ctk_img = ctk.CTkImage(light_image=img, size=(new_w, new_h))
                    self.preview_label.configure(image=ctk_img, text="")
                    self.preview_label.image = ctk_img
                    return
        except Exception:
            pass
        self.preview_label.configure(image="", text="No preview available")

    def _build_variant_section(self, comp_name, component, theme):
        p = self.colors.palette
        self._image_refs[comp_name] = []

        header = ctk.CTkFrame(self.scroll, fg_color=p["accent"], corner_radius=0)
        header.pack(fill="x", pady=(12, 4))
        ctk.CTkLabel(
            header, text=comp_name.upper(),
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=p["text"],
        ).pack(side="left", padx=10, pady=6)

        grid_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        grid_frame.pack(fill="x", pady=(0, 4))
        for col in range(3):
            grid_frame.grid_columnconfigure(col, weight=1, uniform="col")

        variants = component.get("variants", [])
        self.variant_buttons[comp_name] = []

        for i, variant in enumerate(variants):
            row = i // 3
            col = i % 3

            card = ctk.CTkFrame(
                grid_frame, fg_color=p["card_fg"], corner_radius=0,
                border_color=p["border"], border_width=1,
            )
            card.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

            preview_img = self._load_variant_preview(variant, theme)
            if preview_img:
                self._image_refs[comp_name].append(preview_img)

            img_label = ctk.CTkLabel(
                card, text="" if preview_img else "?",
                image=preview_img if preview_img else None,
                width=160, height=107, fg_color="transparent",
                font=ctk.CTkFont(size=28), text_color=p["border"],
            )
            img_label.pack(padx=4, pady=(4, 0))

            name_label = ctk.CTkLabel(
                card, text=variant["name"],
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=p["text"], wraplength=155, justify="center",
            )
            name_label.pack(padx=4, pady=(4, 6))

            def make_handler(cn, vn, c):
                def handler(event=None):
                    self._select_variant(cn, vn, c)
                return handler

            handler = make_handler(comp_name, variant["name"], card)
            card.bind("<Button-1>", handler)
            img_label.bind("<Button-1>", handler)
            name_label.bind("<Button-1>", handler)

            self.variant_buttons[comp_name].append({"name": variant["name"], "frame": card})

        active_variant = self.theme_manager.active_components.get(comp_name)
        if not active_variant and variants:
            active_variant = variants[0]["name"]
        if active_variant:
            for btn_info in self.variant_buttons[comp_name]:
                if btn_info["name"] == active_variant:
                    btn_info["frame"].configure(fg_color=p["active"], border_color=p["accent"])

    def _select_variant(self, comp_name, variant_name, selected_frame):
        p = self.colors.palette
        for btn in self.variant_buttons.get(comp_name, []):
            btn["frame"].configure(fg_color=p["card_fg"], border_color=p["border"])
        selected_frame.configure(fg_color=p["active"], border_color=p["accent"])

        if self.current_theme:
            theme = self.theme_manager.get_theme(self.current_theme)
            if theme:
                components = theme["manifest"].get("components", {})
                component = components.get(comp_name, {})
                for variant in component.get("variants", []):
                    if variant["name"] == variant_name:
                        self._load_preview_image_from_variant(variant, theme)
                        break
        self.on_component_change(comp_name, variant_name)

    def _load_preview_image_from_variant(self, variant, theme):
        try:
            preview_path = variant.get("preview")
            if not preview_path:
                return
            full_path = os.path.join(theme["path"], preview_path)
            if not os.path.exists(full_path):
                return
            img = Image.open(full_path)
            img.thumbnail((600, 200), Image.LANCZOS)
            ctk_img = ctk.CTkImage(light_image=img, size=(img.width, img.height))
            self.preview_label.configure(image=ctk_img, text="")
            self.preview_label.image = ctk_img
        except Exception:
            pass

    def _build_cursor_section(self, comp_name, component, theme):
        p = self.colors.palette
        self._image_refs[comp_name] = []

        header = ctk.CTkFrame(self.scroll, fg_color=p["accent"], corner_radius=0)
        header.pack(fill="x", pady=(12, 4))
        ctk.CTkLabel(
            header, text="CURSORS",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=p["text"],
        ).pack(side="left", padx=10, pady=6)

        cursor_path = component.get("path", "cursors")
        cursor_dir = os.path.join(theme["path"], cursor_path)

        cursor_files = []
        if os.path.isdir(cursor_dir):
            for fname in sorted(os.listdir(cursor_dir)):
                if fname.lower().endswith((".cur", ".ani")):
                    cursor_files.append(fname)

        if not cursor_files:
            ctk.CTkLabel(
                self.scroll,
                text="No cursor previews available" if os.path.isdir(cursor_dir) else "Cursor folder not found",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=p["border"], anchor="w",
            ).pack(fill="x", padx=12, pady=(4, 8))
            return

        grid_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        grid_frame.pack(fill="x", pady=(0, 4))
        for col in range(3):
            grid_frame.grid_columnconfigure(col, weight=1, uniform="cursor_col")

        for i, fname in enumerate(cursor_files):
            row_i = i // 3
            col_i = i % 3

            card = ctk.CTkFrame(
                grid_frame, fg_color=p["card_fg"], corner_radius=0,
                border_color=p["border"], border_width=1,
            )
            card.grid(row=row_i, column=col_i, padx=4, pady=4, sticky="nsew")

            thumb = None
            try:
                full_path = os.path.join(cursor_dir, fname)
                img = Image.open(full_path)
                img = img.resize((48, 48), Image.LANCZOS)
                thumb = ctk.CTkImage(light_image=img, size=(48, 48))
                self._image_refs[comp_name].append(thumb)
            except Exception:
                pass

            ctk.CTkLabel(
                card, text="" if thumb else "?",
                image=thumb if thumb else None,
                width=64, height=64, fg_color=p["accent"],
                font=ctk.CTkFont(size=22), text_color=p["border"],
            ).pack(padx=4, pady=(4, 0))

            ctk.CTkLabel(
                card, text=os.path.splitext(fname)[0],
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color=p["text"], wraplength=90, justify="center",
            ).pack(padx=4, pady=(2, 6))

    def _build_other_section(self, other_components, components, theme):
        p = self.colors.palette

        header = ctk.CTkLabel(
            self.scroll, text="OTHER COMPONENTS",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=p["text"], anchor="w",
        )
        header.pack(fill="x", pady=(16, 8))

        for comp_name in other_components:
            comp = components[comp_name]
            row = ctk.CTkFrame(
                self.scroll, fg_color=p["card_fg"], corner_radius=0,
                border_color=p["border"], border_width=1,
            )
            row.pack(fill="x", pady=2)

            ctk.CTkLabel(
                row, text=comp_name.capitalize(),
                font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                text_color=p["text"], anchor="w",
            ).pack(side="left", padx=10, pady=8)

            detail = ""
            if "mods" in comp:
                detail = f"{len(comp['mods'])} mods"
            elif "variants" in comp:
                detail = f"{len(comp['variants'])} variants"
            elif "path" in comp:
                detail = comp["path"]

            if detail:
                ctk.CTkLabel(
                    row, text=detail,
                    font=ctk.CTkFont(family="Segoe UI", size=10),
                    text_color=p["border"], anchor="e",
                ).pack(side="right", padx=10, pady=8)

    def _load_variant_preview(self, variant, theme):
        try:
            preview_path = variant.get("preview")
            if not preview_path:
                file_path = variant.get("file", "")
                img_exts = {".png", ".jpg", ".jpeg", ".bmp"}
                if any(file_path.lower().endswith(ext) for ext in img_exts):
                    preview_path = file_path
                else:
                    return None

            full_path = os.path.join(theme["path"], preview_path)
            if not os.path.exists(full_path):
                return None

            img = Image.open(full_path)
            img = img.resize((160, 107), Image.LANCZOS)
            return ctk.CTkImage(light_image=img, size=(160, 107))
        except Exception:
            return None
