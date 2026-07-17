"""Component panel — right side in preset mode. Theme-reactive."""

import customtkinter as ctk

from core.manifest_parser import GUIDE_COMPONENT_TYPES
from ui.tooltip import Hovertip


class ComponentPanel(ctk.CTkFrame):
    GUIDE_COMPONENTS = GUIDE_COMPONENT_TYPES

    def __init__(self, parent, theme_manager, colors, on_apply,
                 on_show_result=None, on_guide=None):
        p = colors.palette
        super().__init__(parent, corner_radius=0, fg_color=p["inactive"])
        self.theme_manager = theme_manager
        self.colors = colors
        self.on_apply = on_apply
        self.on_show_result = on_show_result
        self.on_guide = on_guide
        self.current_theme = None
        self.component_vars = {}
        self.component_rows = {}
        self._build()
        self.colors.register(self._on_palette_change)

    def destroy(self):
        """Unregister the palette callback before tearing down."""
        try:
            self.colors.unregister(self._on_palette_change)
        except Exception:
            pass
        super().destroy()

    # ------------------------------------------------------------------
    # Palette change
    # ------------------------------------------------------------------

    def _on_palette_change(self, palette: dict[str, str]):
        if not self.winfo_exists():
            return
        self.configure(fg_color=palette["inactive"])
        # Rebuild the list if a theme is loaded (simpler than per-widget update)
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

        self._header_label = ctk.CTkLabel(
            self._header, text="COMPONENTS",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=p["text"],
        )
        self._header_label.pack(side="left", padx=16, pady=12)

        # Scrollable list
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=p["border"],
            scrollbar_button_hover_color=p["text"],
        )
        self.scroll.pack(fill="both", expand=True, padx=8, pady=8)

        self.placeholder = ctk.CTkLabel(
            self.scroll, text="Select a theme\nto see components",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=p["border"],
        )
        self.placeholder.pack(expand=True, pady=40)

        # Footer buttons
        self._footer = ctk.CTkFrame(self, fg_color=p["accent"], corner_radius=0,
                                     border_color=p["border"], border_width=1)
        self._footer.pack(fill="x", side="bottom")

        self._apply_selected_btn = ctk.CTkButton(
            self._footer, text="Apply Selected",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=p["background"], text_color=p["text"],
            hover_color=p["border"], corner_radius=0,
            border_color=p["border"], border_width=1,
            command=self._on_apply_selected,
        )
        self._apply_selected_btn.pack(fill="x", padx=8, pady=(8, 4))

        self._apply_all_btn = ctk.CTkButton(
            self._footer, text="Apply Full Theme",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            fg_color=p["text"], text_color=p["active"],
            hover_color=p["border"], corner_radius=0,
            command=self._on_apply_all,
        )
        self._apply_all_btn.pack(fill="x", padx=8, pady=(4, 8))

    def load_theme(self, theme_name: str):
        self.current_theme = theme_name
        theme = self.theme_manager.get_theme(theme_name)
        if not theme:
            return

        for widget in self.scroll.winfo_children():
            widget.destroy()
        self.component_vars = {}
        self.component_rows = {}

        manifest = theme["manifest"]
        components = manifest.get("components", {})
        p = self.colors.palette

        # Update header/footer colors
        self._header.configure(fg_color=p["accent"], border_color=p["border"])
        self._header_label.configure(text_color=p["text"])
        self._footer.configure(fg_color=p["accent"], border_color=p["border"])
        self._apply_selected_btn.configure(
            fg_color=p["background"], text_color=p["text"],
            hover_color=p["border"], border_color=p["border"],
        )
        self._apply_all_btn.configure(
            fg_color=p["text"], text_color=p["active"], hover_color=p["border"],
        )

        for comp_name, comp_data in components.items():
            self._build_component_row(comp_name, comp_data, p)

    def _build_component_row(self, comp_name, comp_data, p):
        row = ctk.CTkFrame(
            self.scroll, fg_color=p["background"], corner_radius=0,
            border_color=p["border"], border_width=1,
        )
        row.pack(fill="x", pady=2)

        var = ctk.BooleanVar(value=True)
        self.component_vars[comp_name] = var

        ctk.CTkCheckBox(
            row, text="", variable=var, width=20,
            checkbox_width=16, checkbox_height=16,
            corner_radius=0, fg_color=p["accent"],
            border_color=p["border"], hover_color=p["text"],
            checkmark_color=p["text"],
        ).pack(side="left", padx=(8, 4), pady=8)

        ctk.CTkLabel(
            row, text=comp_name.capitalize(),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=p["text"], anchor="w",
        ).pack(side="left", padx=4, pady=8)

        # Detail info
        detail = self._get_detail(comp_name, comp_data)
        if detail:
            ctk.CTkLabel(
                row, text=detail,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color=p["border"], anchor="e",
            ).pack(side="right", padx=8, pady=8)

        # Action button
        is_guide = comp_name in self.GUIDE_COMPONENTS
        btn_text = "?" if is_guide else ">"
        btn_cmd = (
            (lambda cn=comp_name: self.on_guide(cn) if self.on_guide else None)
            if is_guide
            else (lambda cn=comp_name: self.on_apply(cn))
        )

        action_btn = ctk.CTkButton(
            row, text=btn_text, width=24, height=24,
            fg_color=p["border"] if is_guide else p["accent"],
            text_color=p["text"], hover_color=p["border"],
            corner_radius=0,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=btn_cmd,
        )
        action_btn.pack(side="right", padx=(4, 8), pady=8)
        Hovertip(
            action_btn,
            "Open manual setup guide" if is_guide else "Apply this component now",
        )

        if is_guide:
            ctk.CTkLabel(
                row, text="manual setup",
                font=ctk.CTkFont(family="Segoe UI", size=10),
                text_color=p["border"], anchor="e",
            ).pack(side="right", padx=(0, 4))

        self.component_rows[comp_name] = row

    def _get_detail(self, comp_name, comp_data):
        if "variants" in comp_data:
            active = self.theme_manager.active_components.get(comp_name)
            if active:
                return active[:20] + "..." if len(active) > 20 else active
            return f"{len(comp_data['variants'])} variants"
        if "mods" in comp_data:
            return f"{len(comp_data['mods'])} mods"
        if "path" in comp_data:
            return "folder"
        if "schemes" in comp_data:
            return "scheme"
        if "userChrome" in comp_data:
            return "css"
        return ""

    def update_selection(self, component_type, variant_name):
        p = self.colors.palette
        row = self.component_rows.get(component_type)
        if row:
            row.configure(fg_color=p["inactive"], border_color=p["accent"])

    def _on_apply_selected(self):
        if not self.current_theme:
            return
        for comp_name, var in self.component_vars.items():
            if var.get():
                self.on_apply(comp_name)

    def _on_apply_all(self):
        self.on_apply(None)