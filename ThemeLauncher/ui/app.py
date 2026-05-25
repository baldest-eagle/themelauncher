"""
Main Application — Theme Launcher.

Three modes: Presets, Mixer, Studio.
Status bar at the bottom for feedback.

The GUI itself reflects the active theme's palette via ThemeColors.
When a theme is selected or applied, the entire UI recolors.
"""

import os
import threading
from tkinter import filedialog

import customtkinter as ctk

from core.applier import Applier
from core.asset_studio import CursorSetManager, IconSetManager
from core.logger import log
from core.mixer import Mixer
from core.theme_colors import ThemeColors
from ui.asset_studio_panel import AssetStudioPanel
from ui.component_panel import ComponentPanel
from ui.guide_dialog import GuideDialog
from ui.mix_recipe_panel import MixRecipePanel
from ui.mixer_panel import MixerPanel
from ui.preview_panel import PreviewPanel
from ui.theme_card import ThemeCard


class App(ctk.CTk):
    def __init__(self, theme_manager_or_sdk):
        super().__init__()
        from themelauncher.sdk import ThemeSDK
        if isinstance(theme_manager_or_sdk, ThemeSDK):
            self.sdk = theme_manager_or_sdk
            self.theme_manager = theme_manager_or_sdk.theme_manager
        else:
            self.sdk = None
            self.theme_manager = theme_manager_or_sdk
        self.selected_theme: str | None = None
        self._mode = "preset"  # "preset" | "mixer" | "studio"

        # ── Theme-reactive color system ──
        raw_palette = self.theme_manager.get_active_palette()
        self.colors = ThemeColors(raw_palette)

        # Shared Applier instance
        self.applier = Applier(theme_manager)

        self.title("Theme Launcher")
        self.geometry("1200x800")
        self.minsize(900, 600)
        self.configure(fg_color=self.colors.p("background"))

        # Mixer lives for the lifetime of the app
        self.mixer = Mixer(self.theme_manager)
        self.icon_manager = IconSetManager()
        self.cursor_manager = CursorSetManager(self.theme_manager)

        self._build_layout()
        self._populate_theme_list()

        # Auto-select the active theme if it exists
        active = self.theme_manager.active_theme
        if active and active in self.theme_manager.get_all_themes():
            self._on_theme_selected(active)

        # Register self for palette updates (window bg, status bar, etc.)
        self.colors.register(self._on_palette_change)

    # ------------------------------------------------------------------
    # Palette change handler — recolor the window chrome
    # ------------------------------------------------------------------

    def _on_palette_change(self, palette: dict[str, str]):
        """Recolor top-level widgets that aren't owned by a panel."""
        self.configure(fg_color=palette["background"])
        self.sidebar.configure(fg_color=palette["accent"], border_color=palette["border"])
        self.center_frame.configure(fg_color=palette["background"], border_color=palette["border"])
        self.right_frame.configure(fg_color=palette["inactive"], border_color=palette["border"])
        self.studio_container.configure(fg_color=palette["background"], border_color=palette["border"])
        self.status_bar.configure(fg_color=palette["accent"], border_color=palette["border"])
        self.status_label.configure(text_color=palette["status_fg"])

        # Re-color mode buttons to reflect current mode
        if self._mode == "preset":
            self._style_mode_buttons(preset_active=True)
        elif self._mode == "mixer":
            self._style_mode_buttons(mixer_active=True)
        else:
            self._style_mode_buttons(studio_active=True)

        # Sidebar action buttons
        p = palette
        self.import_button.configure(
            fg_color=p["active"], text_color=p["background"], hover_color=p["border"],
        )
        self.delete_button.configure(
            fg_color=p["danger"], text_color="#FFFFFF", hover_color=p["danger_hover"],
        )
        self.restore_button.configure(
            fg_color=p["accent"], text_color=p["text"], hover_color=p["border"],
        )

        # Refresh theme cards (they hold their own palette ref)
        for card in self._card_widgets:
            card.update_palette(palette)

    # ------------------------------------------------------------------
    # LAYOUT
    # ------------------------------------------------------------------

    def _build_layout(self):
        p = self.colors.palette  # initial snapshot

        # ── SIDEBAR ──
        self.sidebar = ctk.CTkFrame(
            self, width=220, corner_radius=0,
            fg_color=p["accent"], border_color=p["border"], border_width=1,
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.sidebar, text="THEMES",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=p["text"],
        ).pack(pady=(16, 8), padx=12, anchor="w")

        # Mode toggle
        mode_bar = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        mode_bar.pack(fill="x", padx=12, pady=(0, 8))
        for col in range(3):
            mode_bar.grid_columnconfigure(col, weight=1)

        self.preset_mode_btn = ctk.CTkButton(
            mode_bar, text="Presets",
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            fg_color=p["active"], text_color=p["background"],
            hover_color=p["border"], corner_radius=0,
            command=self._enter_preset_mode,
        )
        self.preset_mode_btn.grid(row=0, column=0, sticky="ew", padx=(0, 1))

        self.mixer_mode_btn = ctk.CTkButton(
            mode_bar, text="Mixer",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color=p["inactive"], text_color=p["text"],
            hover_color=p["border"], corner_radius=0,
            command=self._enter_mixer_mode,
        )
        self.mixer_mode_btn.grid(row=0, column=1, sticky="ew", padx=(1, 1))

        self.studio_mode_btn = ctk.CTkButton(
            mode_bar, text="Studio",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            fg_color=p["inactive"], text_color=p["text"],
            hover_color=p["border"], corner_radius=0,
            command=self._enter_studio_mode,
        )
        self.studio_mode_btn.grid(row=0, column=2, sticky="ew", padx=(1, 0))

        # Sidebar action buttons
        self.import_button = ctk.CTkButton(
            self.sidebar, text="Import Theme",
            fg_color=p["active"], text_color=p["background"],
            hover_color=p["border"], corner_radius=0,
            command=self._import_theme,
        )
        self.import_button.pack(fill="x", padx=12, pady=(0, 4))

        self.delete_button = ctk.CTkButton(
            self.sidebar, text="Delete Selected",
            fg_color=p["danger"], text_color="#FFFFFF",
            hover_color=p["danger_hover"], corner_radius=0,
            command=self._delete_selected_theme,
        )
        self.delete_button.pack(fill="x", padx=12, pady=(0, 4))

        self.restore_button = ctk.CTkButton(
            self.sidebar, text="Restore System Defaults",
            fg_color=p["accent"], text_color=p["text"],
            hover_color=p["border"], corner_radius=0,
            command=self._restore_system_defaults,
        )
        self.restore_button.pack(fill="x", padx=12, pady=(0, 8))

        # Scrollable theme list
        self.theme_scroll = ctk.CTkScrollableFrame(
            self.sidebar, fg_color="transparent",
            scrollbar_button_color=p["border"],
            scrollbar_button_hover_color=p["text"],
        )
        self.theme_scroll.pack(fill="both", expand=True, padx=4, pady=4)

        # ── CENTER ──
        self.center_frame = ctk.CTkFrame(
            self, corner_radius=0, fg_color=p["background"],
            border_color=p["border"], border_width=1,
        )
        self.center_frame.pack(side="left", fill="both", expand=True)

        self.preview_panel = PreviewPanel(
            self.center_frame, theme_manager=self.theme_manager,
            colors=self.colors, on_component_change=self._on_component_change,
        )
        self.preview_panel.pack(fill="both", expand=True)

        self.mixer_panel = MixerPanel(
            self.center_frame, mixer=self.mixer, colors=self.colors,
            on_slot_change=self._on_mixer_slot_change,
        )

        # ── RIGHT ──
        self.right_frame = ctk.CTkFrame(
            self, width=280, corner_radius=0,
            fg_color=p["inactive"], border_color=p["border"], border_width=1,
        )
        self.right_frame.pack(side="right", fill="y")
        self.right_frame.pack_propagate(False)

        self.component_panel = ComponentPanel(
            self.right_frame, theme_manager=self.theme_manager,
            colors=self.colors, on_apply=self._on_apply,
            on_show_result=self._show_result, on_guide=self._on_guide,
        )
        self.component_panel.pack(fill="both", expand=True)

        self.mix_recipe_panel = MixRecipePanel(
            self.right_frame, mixer=self.mixer, colors=self.colors,
            on_apply_mix=self._on_apply_mix, on_save_mix=self._on_save_mix,
        )

        # Studio — full-width container
        self.studio_container = ctk.CTkFrame(
            self, corner_radius=0, fg_color=p["background"],
            border_color=p["border"], border_width=1,
        )

        self.asset_studio_panel = AssetStudioPanel(
            self.studio_container,
            icon_manager=self.icon_manager, cursor_manager=self.cursor_manager,
            colors=self.colors, theme_manager=self.theme_manager,
        )
        self.asset_studio_panel.pack(fill="both", expand=True)

        # ── STATUS BAR ──
        self.status_bar = ctk.CTkFrame(
            self, height=28, corner_radius=0,
            fg_color=p["accent"], border_color=p["border"], border_width=1,
        )
        self.status_bar.pack(side="bottom", fill="x")
        self.status_bar.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            self.status_bar, text="Ready",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=p["status_fg"], anchor="w",
        )
        self.status_label.pack(side="left", padx=12, pady=4)

        self._card_widgets: list[ThemeCard] = []

    # ------------------------------------------------------------------
    # Mode button styling helper
    # ------------------------------------------------------------------

    def _style_mode_buttons(self, preset_active=False, mixer_active=False, studio_active=False):
        p = self.colors.palette
        if preset_active:
            self.preset_mode_btn.configure(fg_color=p["active"], text_color=p["background"],
                                           font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"))
        else:
            self.preset_mode_btn.configure(fg_color=p["inactive"], text_color=p["text"],
                                           font=ctk.CTkFont(family="Segoe UI", size=10))
        if mixer_active:
            self.mixer_mode_btn.configure(fg_color=p["active"], text_color=p["background"],
                                          font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"))
        else:
            self.mixer_mode_btn.configure(fg_color=p["inactive"], text_color=p["text"],
                                          font=ctk.CTkFont(family="Segoe UI", size=10))
        if studio_active:
            self.studio_mode_btn.configure(fg_color=p["active"], text_color=p["background"],
                                           font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"))
        else:
            self.studio_mode_btn.configure(fg_color=p["inactive"], text_color=p["text"],
                                           font=ctk.CTkFont(family="Segoe UI", size=10))

    # ------------------------------------------------------------------
    # Mode switching
    # ------------------------------------------------------------------

    def _enter_preset_mode(self):
        if self._mode == "preset":
            return

        if self._mode == "studio":
            self.studio_container.pack_forget()
            self.center_frame.pack(side="left", fill="both", expand=True)
            self.right_frame.pack(side="right", fill="y")

        self._mode = "preset"
        self.mixer_panel.pack_forget()
        self.preview_panel.pack(fill="both", expand=True)
        self.mix_recipe_panel.pack_forget()
        self.component_panel.pack(fill="both", expand=True)

        self._style_mode_buttons(preset_active=True)

        self.import_button.pack(fill="x", padx=12, pady=(0, 4))
        self.delete_button.pack(fill="x", padx=12, pady=(0, 4))

        title = f"Theme Launcher — {self.selected_theme}" if self.selected_theme else "Theme Launcher"
        self.title(title)
        self._set_status("Preset mode")

    def _enter_mixer_mode(self):
        if self._mode == "mixer":
            return

        if self._mode == "studio":
            self.studio_container.pack_forget()
            self.center_frame.pack(side="left", fill="both", expand=True)
            self.right_frame.pack(side="right", fill="y")

        self._mode = "mixer"
        self.preview_panel.pack_forget()
        self.mixer_panel.pack(fill="both", expand=True)
        self.component_panel.pack_forget()
        self.mix_recipe_panel.pack(fill="both", expand=True)

        self._style_mode_buttons(mixer_active=True)

        self.import_button.pack_forget()
        self.delete_button.pack_forget()

        self.mixer_panel.load_catalog()
        self.mix_recipe_panel.refresh()
        self.title("Theme Launcher — Mixer")
        self._set_status("Mixer mode — pick one component per slot from any theme")

    def _enter_studio_mode(self):
        if self._mode == "studio":
            return
        self._mode = "studio"

        self.preview_panel.pack_forget()
        self.mixer_panel.pack_forget()
        self.component_panel.pack_forget()
        self.mix_recipe_panel.pack_forget()
        self.center_frame.pack_forget()
        self.right_frame.pack_forget()

        self.studio_container.pack(side="left", fill="both", expand=True)

        self._style_mode_buttons(studio_active=True)

        self.import_button.pack_forget()
        self.delete_button.pack_forget()
        self.title("Theme Launcher — Studio")
        self._set_status("Asset Studio — manage icon and cursor sets")

    # ------------------------------------------------------------------
    # Theme list
    # ------------------------------------------------------------------

    def _populate_theme_list(self):
        for theme_name, theme_data in self.theme_manager.get_all_themes().items():
            card = ThemeCard(
                self.theme_scroll, theme_name=theme_name,
                theme_data=theme_data, colors=self.colors,
                on_select=self._on_theme_selected,
            )
            card.pack(fill="x", padx=4, pady=2)
            self._card_widgets.append(card)

    def _refresh_theme_list(self):
        for widget in self.theme_scroll.winfo_children():
            widget.destroy()
        self._card_widgets.clear()
        self._populate_theme_list()

    # ------------------------------------------------------------------
    # Preset mode handlers
    # ------------------------------------------------------------------

    def _on_theme_selected(self, theme_name: str):
        # Deselect all other cards
        for card in self._card_widgets:
            card.set_selected(card.theme_name == theme_name)

        self.selected_theme = theme_name

        # ── Update the GUI palette to reflect the selected theme ──
        theme = self.theme_manager.get_theme(theme_name)
        if theme:
            raw_palette = theme["manifest"].get("palette", {})
            self.colors.update_palette(raw_palette)

        self.preview_panel.load_theme(theme_name)
        self.component_panel.load_theme(theme_name)
        self.title(f"Theme Launcher — {theme_name}")
        self._set_status(f"Selected: {theme_name}")

    def _import_theme(self):
        folder = filedialog.askdirectory(title="Select Theme Folder")
        if not folder:
            return
        self._set_status("Importing theme...")
        result = self.theme_manager.import_theme_folder(folder)
        self._show_result(result)
        if result["success"]:
            self._refresh_theme_list()
            theme_name = result.get("theme_name")
            if theme_name and theme_name in self.theme_manager.get_all_themes():
                self._on_theme_selected(theme_name)

    def _delete_selected_theme(self):
        if not self.selected_theme:
            self._show_result({"success": False, "message": "No theme selected."})
            return
        self._confirm_delete(self.selected_theme)

    def _confirm_delete(self, theme_name: str):
        p = self.colors.palette
        dialog = ctk.CTkToplevel(self)
        dialog.title("Confirm Delete")
        dialog.geometry("420x200")
        dialog.configure(fg_color=p["background"])
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text=f'Delete "{theme_name}"?\nThis will remove the theme folder permanently.',
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=p["text"], wraplength=380,
        ).pack(expand=True, padx=20, pady=20)

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(pady=(0, 20))

        ctk.CTkButton(
            btn_row, text="Cancel",
            fg_color=p["accent"], text_color=p["text"],
            hover_color=p["border"], corner_radius=0,
            command=dialog.destroy,
        ).pack(side="left", padx=8)

        def do_delete():
            dialog.destroy()
            self._set_status(f"Deleting {theme_name}...")
            result = self.theme_manager.delete_theme(theme_name)
            self._show_result(result)
            if result["success"]:
                self.selected_theme = None
                self.title("Theme Launcher")
                self._refresh_theme_list()
                # Reset palette to default if the deleted theme was active
                if self.theme_manager.active_theme is None:
                    self.colors.reset_to_default()

        ctk.CTkButton(
            btn_row, text="Delete",
            fg_color=p["danger"], text_color="#FFFFFF",
            hover_color=p["danger_hover"], corner_radius=0,
            command=do_delete,
        ).pack(side="left", padx=8)

    def _restore_system_defaults(self):
        self._set_status("Restoring system defaults...")
        if self.sdk:
            try:
                snaps = self.sdk.list_snapshots()
                if snaps:
                    self._set_status("Restoring via Smart Rollback...")
                    result = self.sdk.restore_snapshot()
                    if result["success"]:
                        self._show_result({
                            "success": True,
                            "message": f"Smart Rollback successful!\nRestored from snapshot baseline: {result['from_snapshot']}\nRestored elements: {', '.join(result['restored'])}"
                        })
                        self._set_status("System defaults restored via Smart Rollback")
                        self.colors.reset_to_default()
                        return
            except Exception as e:
                log.warning("Smart Rollback failed, falling back to static restore: %s", e)

        results = self.applier.restore_defaults()
        combined = {
            "success": all(r["success"] for r in results.values()),
            "message": "System Restore Results:\n" + "\n".join(f"{k}: {v['message']}" for k, v in results.items()),
        }
        self._show_result(combined)
        self._set_status("System defaults restored")
        # Reset GUI to default palette
        self.colors.reset_to_default()

    def _on_component_change(self, component_type: str, variant_name: str):
        self.theme_manager.set_active_component(component_type, variant_name)
        self.component_panel.update_selection(component_type, variant_name)

    def _on_apply(self, component_type: str | None = None):
        if not self.selected_theme:
            return
        if self.theme_manager.active_theme != self.selected_theme:
            self.theme_manager.set_active_theme(self.selected_theme)

        # Capture safety snapshot before making changes
        if self.sdk:
            try:
                self._set_status("Capturing safety snapshot...")
                snap_id = self.sdk.capture_snapshot()
                log.info("Safety snapshot captured: %s", snap_id)
            except Exception as e:
                log.warning("Could not capture safety snapshot: %s", e)

        self._set_status("Applying theme...")

        if component_type:
            variant = self.theme_manager.active_components.get(component_type)
            result = self.applier.apply_component(self.selected_theme, component_type, variant)
            if result.get("guide"):
                self._open_guide(component_type, result)
            else:
                self._show_result(result)
            self._set_status(f"Applied {component_type}")
        else:
            results = self.applier.apply_full_theme(self.selected_theme)
            guide_results = {k: v for k, v in results.items() if v.get("guide")}
            apply_results = {k: v for k, v in results.items() if not v.get("guide")}
            if apply_results:
                combined = {
                    "success": all(r["success"] for r in apply_results.values()),
                    "message": "\n".join(f"{k}: {v['message']}" for k, v in apply_results.items()),
                }
                self._show_result(combined)
            for comp_type, result in guide_results.items():
                self._open_guide(comp_type, result)
            self._set_status("Full theme applied")

    def _on_guide(self, component_type: str):
        if not self.selected_theme:
            return
        result = self.applier.apply_component(self.selected_theme, component_type)
        if result.get("guide"):
            self._open_guide(component_type, result)
        else:
            self._show_result(result)

    def _open_guide(self, component_type: str, result: dict):
        guide_path = result.get("guide_path")
        app_key = result.get("app", component_type)

        steps = []
        auto_msg = result.get("message", "")
        if auto_msg and "Opening guide" not in auto_msg:
            steps.append({"title": "Automated", "instruction": auto_msg})

        if guide_path and os.path.isdir(guide_path):
            img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
            images = sorted(f for f in os.listdir(guide_path) if os.path.splitext(f)[1].lower() in img_exts)
            for img_file in images:
                name = os.path.splitext(img_file)[0]
                title = name.replace("-", " ").replace("_", " ").title()
                steps.append({
                    "title": title,
                    "instruction": "Match your settings to the screenshot below.",
                    "image": os.path.join(guide_path, img_file),
                })

        if not steps:
            steps.append({
                "title": "Manual Setup Required",
                "instruction": f"Open {component_type.title()} and apply the theme settings manually.",
            })

        titles = {
            "startallback": "StartAllBack Setup Guide",
            "mica": "MicaForEveryone Setup Guide",
            "oldnewexplorer": "OldNewExplorer Setup Guide",
        }
        title = titles.get(component_type, f"{component_type.title()} Setup Guide")

        GuideDialog(self, title=title, colors=self.colors, steps=steps, app_name=app_key)

    # ------------------------------------------------------------------
    # Mixer mode handlers
    # ------------------------------------------------------------------

    def _on_mixer_slot_change(self, comp_type, theme_name, variant_name):
        self.mix_recipe_panel.refresh()

    def _on_apply_mix(self):
        if not self.mixer.mix:
            self._show_result({"success": False, "message": "Your mix is empty — select some components first."})
            return
        self._set_status("Applying mix...")
        results = self.mixer.apply_mix()
        combined = {
            "success": all(r["success"] for r in results.values()),
            "message": "\n".join(f"{k}: {v['message']}" for k, v in results.items()),
        }
        self._show_result(combined)
        self._set_status("Mix applied")

    def _on_save_mix(self, name, description, author):
        result = self.mixer.save_as_theme(name, description, author)
        self._show_result(result)
        if result["success"]:
            self._refresh_theme_list()
            self._enter_preset_mode()
            new_name = result.get("theme_name", name)
            if new_name in self.theme_manager.get_all_themes():
                self._on_theme_selected(new_name)

    # ------------------------------------------------------------------
    # Shared UI helpers
    # ------------------------------------------------------------------

    def _show_result(self, result: dict):
        p = self.colors.palette
        dialog = ctk.CTkToplevel(self)
        dialog.title("Result")
        dialog.geometry("460x240")
        dialog.configure(fg_color=p["background"])
        dialog.grab_set()

        icon = "OK" if result["success"] else "X"
        color = p["success"] if result["success"] else p["error"]

        # Status icon label
        ctk.CTkLabel(
            dialog, text=icon,
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=color,
        ).pack(pady=(20, 0))

        ctk.CTkLabel(
            dialog, text=result["message"],
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=p["text"], wraplength=420, justify="left",
        ).pack(expand=True, padx=24, pady=(8, 16))

        ctk.CTkButton(
            dialog, text="OK",
            fg_color=p["accent"], text_color=p["text"],
            hover_color=p["border"], corner_radius=0,
            command=dialog.destroy,
        ).pack(pady=(0, 16))

    def _set_status(self, message: str):
        self.status_label.configure(text=message)
        log.info("Status: %s", message)