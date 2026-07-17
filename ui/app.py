"""
Main Application — Theme Launcher.

Three modes: Presets, Mixer, Studio.
Status bar at the bottom for feedback.

The GUI itself reflects the active theme's palette via ThemeColors.
When a theme is selected or applied, the entire UI recolors.
"""

import json
import os
import threading
from tkinter import filedialog, messagebox

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

# Window-state persistence: a small JSON file under LOCALAPPDATA (Windows)
# or ~/.themelauncher (Linux/macOS).  Stores geometry + last mode + last
# selected theme so the app restores its previous session on restart.
_SETTINGS_PATH = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~/.themelauncher")),
    "themelauncher_ui.json",
)


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
        self.applier = Applier(self.theme_manager)

        self.title("Theme Launcher")
        self.geometry("1200x800")
        # minsize matches the actual layout budget: sidebar 220 + right 280
        # = 500px of chrome + 480px center grid; 1100x680 keeps the center
        # column from clipping at the smallest legal size.
        self.minsize(1100, 680)
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

        # Async / busy state
        self._busy = False
        self._result_dialog = None  # set by _show_result; reused to prevent stacking

        # Persist window geometry + mode across restarts.
        self._load_window_state()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._bind_shortcuts()

    # ------------------------------------------------------------------
    # Palette change handler — recolor the window chrome
    # ------------------------------------------------------------------

    def _on_palette_change(self, palette: dict[str, str]):
        """Recolor top-level widgets that aren't owned by a panel."""
        if not self.winfo_exists():
            return
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
            fg_color=p["danger"], text_color=p["background"], hover_color=p["danger_hover"],
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

        # Cache two CTkFont instances for mode buttons so we don't allocate
        # a fresh one on every palette change.
        self._mode_font_bold = ctk.CTkFont(family="Segoe UI", size=10, weight="bold")
        self._mode_font_regular = ctk.CTkFont(family="Segoe UI", size=10)

        # Single shared result dialog — destroyed/recreated per show to
        # prevent stacked modal grabs.
        self._result_dialog = None

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
            font=self._mode_font_bold,
            fg_color=p["active"], text_color=p["background"],
            hover_color=p["border"], corner_radius=0,
            command=self._enter_preset_mode,
        )
        self.preset_mode_btn.grid(row=0, column=0, sticky="ew", padx=(0, 1))

        self.mixer_mode_btn = ctk.CTkButton(
            mode_bar, text="Mixer",
            font=self._mode_font_regular,
            fg_color=p["inactive"], text_color=p["text"],
            hover_color=p["border"], corner_radius=0,
            command=self._enter_mixer_mode,
        )
        self.mixer_mode_btn.grid(row=0, column=1, sticky="ew", padx=(1, 1))

        self.studio_mode_btn = ctk.CTkButton(
            mode_bar, text="Studio",
            font=self._mode_font_regular,
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
            fg_color=p["danger"], text_color=p["background"],
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
            on_error=self._set_status,
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
                                           font=self._mode_font_bold)
        else:
            self.preset_mode_btn.configure(fg_color=p["inactive"], text_color=p["text"],
                                           font=self._mode_font_regular)
        if mixer_active:
            self.mixer_mode_btn.configure(fg_color=p["active"], text_color=p["background"],
                                          font=self._mode_font_bold)
        else:
            self.mixer_mode_btn.configure(fg_color=p["inactive"], text_color=p["text"],
                                          font=self._mode_font_regular)
        if studio_active:
            self.studio_mode_btn.configure(fg_color=p["active"], text_color=p["background"],
                                           font=self._mode_font_bold)
        else:
            self.studio_mode_btn.configure(fg_color=p["inactive"], text_color=p["text"],
                                           font=self._mode_font_regular)

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
        # Idempotent: tear down any existing children + clear the cache
        # before repopulating.  Belt-and-suspenders — _refresh_theme_list
        # already clears, but a stray double-call would otherwise duplicate
        # cards in _card_widgets and confuse _on_palette_change.
        for widget in self.theme_scroll.winfo_children():
            widget.destroy()
        self._card_widgets = []

        themes = self.theme_manager.get_all_themes()
        if not themes:
            # Empty-state placeholder so the sidebar isn't just blank.
            p = self.colors.palette
            ctk.CTkLabel(
                self.theme_scroll,
                text="No themes found.\nImport a theme folder to get started.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=p["border"], justify="center",
            ).pack(expand=True, pady=40)
            return

        for theme_name, theme_data in themes.items():
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
        self._card_widgets = []
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

        def _do():
            return self.theme_manager.import_theme_folder(folder)

        self._run_async(
            "Importing theme...",
            _do,
            on_done=self._on_import_done,
        )

    def _on_import_done(self, result):
        self._show_result(result)
        if result.get("success"):
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
        dialog.transient(self)
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

            def _do():
                return self.theme_manager.delete_theme(theme_name)

            self._run_async(
                f"Deleting {theme_name}...",
                _do,
                on_done=lambda r: self._on_delete_done(r, theme_name),
            )

        ctk.CTkButton(
            btn_row, text="Delete",
            fg_color=p["danger"], text_color=p["background"],
            hover_color=p["danger_hover"], corner_radius=0,
            command=do_delete,
        ).pack(side="left", padx=8)

    def _on_delete_done(self, result, theme_name):
        self._show_result(result)
        if result.get("success"):
            self.selected_theme = None
            self.title("Theme Launcher")
            self._refresh_theme_list()
            # Reset palette to default if the deleted theme was active
            if self.theme_manager.active_theme is None:
                self.colors.reset_to_default()

    def _restore_system_defaults(self):
        # Destructive system-wide operation — require explicit confirmation.
        if not messagebox.askyesno(
            "Restore System Defaults",
            "This will overwrite your current registry, msstyles, cursors, "
            "and other system theme settings with the Windows defaults.\n\n"
            "Any unsaved mix will be lost. Continue?",
        ):
            return

        self._set_status("Restoring system defaults...")

        def _do():
            if self.sdk:
                try:
                    snaps = self.sdk.list_snapshots()
                    if snaps:
                        # Tk is not thread-safe — marshal UI updates via after().
                        self.after(0, lambda: self._set_status("Restoring via Smart Rollback..."))
                        result = self.sdk.restore_snapshot()
                        if isinstance(result, dict) and result.get("success"):
                            return {
                                "kind": "snapshot",
                                "from_snapshot": result.get("from_snapshot"),
                                "restored": result.get("restored", []),
                            }
                except Exception as e:
                    log.warning("Smart Rollback failed, falling back to static restore: %s", e)
            return {"kind": "static", "results": self.applier.restore_defaults()}

        self._run_async(
            "Restoring system defaults...",
            _do,
            on_done=self._on_restore_done,
        )

    def _on_restore_done(self, payload):
        if not isinstance(payload, dict):
            self._set_status("Restore failed: unexpected result", severity="error")
            return

        if payload.get("kind") == "snapshot":
            restored = payload.get("restored", [])
            self._show_result({
                "success": True,
                "message": (
                    "Smart Rollback successful!\n"
                    f"Restored from snapshot baseline: {payload.get('from_snapshot')}\n"
                    f"Restored elements: {', '.join(restored) if restored else 'none'}"
                ),
            })
            self._set_status("System defaults restored via Smart Rollback", severity="success")
        else:
            results = payload.get("results", {}) or {}
            combined = {
                "success": bool(results) and all(r.get("success") for r in results.values()),
                "message": "System Restore Results:\n" + "\n".join(
                    f"{k}: {v.get('message', '')}" for k, v in results.items()
                ),
            }
            self._show_result(combined)
            self._set_status(
                "System defaults restored" if combined["success"] else "Restore completed with errors",
                severity="success" if combined["success"] else "warning",
            )
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

        self._set_status("Applying theme...")

        if component_type:
            variant = self.theme_manager.active_components.get(component_type)

            def _do():
                # Capture safety snapshot inside the worker so the UI
                # doesn't freeze during capture + apply.
                if self.sdk:
                    try:
                        self.after(0, lambda: self._set_status("Capturing safety snapshot..."))
                        snap_id = self.sdk.capture_snapshot()
                        log.info("Safety snapshot captured: %s", snap_id)
                    except Exception as e:
                        log.warning("Could not capture safety snapshot: %s", e)
                self.after(0, lambda: self._set_status("Applying component..."))
                return self.applier.apply_component(self.selected_theme, component_type, variant)

            self._run_async(
                "Applying theme...",
                _do,
                on_done=self._on_apply_component_done,
            )
        else:
            def _do_full():
                if self.sdk:
                    try:
                        self.after(0, lambda: self._set_status("Capturing safety snapshot..."))
                        snap_id = self.sdk.capture_snapshot()
                        log.info("Safety snapshot captured: %s", snap_id)
                    except Exception as e:
                        log.warning("Could not capture safety snapshot: %s", e)
                self.after(0, lambda: self._set_status("Applying full theme..."))
                return self.applier.apply_full_theme(self.selected_theme)

            self._run_async(
                "Applying full theme...",
                _do_full,
                on_done=self._on_apply_full_done,
            )

    def _on_apply_component_done(self, result):
        if not isinstance(result, dict):
            self._set_status("Apply failed: unexpected result", severity="error")
            return
        if result.get("guide"):
            self._open_guide(result.get("app", ""), result)
        else:
            self._show_result(result)
        self._set_status(f"Applied", severity="success" if result.get("success") else "error")

    def _on_apply_full_done(self, results):
        if not isinstance(results, dict):
            self._set_status("Apply failed: unexpected result", severity="error")
            return
        guide_results = {k: v for k, v in results.items() if v.get("guide")}
        apply_results = {k: v for k, v in results.items() if not v.get("guide")}
        if apply_results:
            combined = {
                "success": all(r.get("success") for r in apply_results.values()),
                "message": "\n".join(f"{k}: {v.get('message', '')}" for k, v in apply_results.items()),
            }
            self._show_result(combined)
        for _comp_type, result in guide_results.items():
            self._open_guide(result.get("app", _comp_type), result)
        self._set_status(
            "Full theme applied" if not guide_results else "Full theme applied (with guides)",
            severity="success" if not guide_results else "warning",
        )

    def _on_guide(self, component_type: str):
        if not self.selected_theme:
            return

        def _do():
            return self.applier.apply_component(self.selected_theme, component_type)

        self._run_async(
            "Loading guide...",
            _do,
            on_done=lambda r: self._on_guide_done(component_type, r),
        )

    def _on_guide_done(self, component_type, result):
        if not isinstance(result, dict):
            return
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
            self._show_result({
                "success": False,
                "message": "Your mix is empty — select some components first.",
            })
            return
        self._set_status("Applying mix...")

        def _do():
            return self.mixer.apply_mix()

        self._run_async(
            "Applying mix...",
            _do,
            on_done=self._on_apply_mix_done,
        )

    def _on_apply_mix_done(self, results):
        if not isinstance(results, dict):
            self._set_status("Mix apply failed: unexpected result", severity="error")
            return
        combined = {
            "success": all(r.get("success") for r in results.values()),
            "message": "\n".join(f"{k}: {v.get('message', '')}" for k, v in results.items()),
        }
        self._show_result(combined)
        self._set_status(
            "Mix applied" if combined["success"] else "Mix applied with errors",
            severity="success" if combined["success"] else "warning",
        )

    def _on_save_mix(self, name, description, author):
        result = self.mixer.save_as_theme(name, description, author)
        self._show_result(result)
        if isinstance(result, dict) and result.get("success"):
            self._refresh_theme_list()
            self._enter_preset_mode()
            new_name = result.get("theme_name", name)
            if new_name in self.theme_manager.get_all_themes():
                self._on_theme_selected(new_name)

    # ------------------------------------------------------------------
    # Async infrastructure — run blocking work off the Tk main thread
    # ------------------------------------------------------------------

    def _run_async(self, label, fn, on_done=None):
        """Run ``fn`` on a daemon thread; marshal the result back to Tk via
        ``self.after(0, ...)``.  Disables sidebar buttons while running so
        the user can't queue overlapping destructive ops.  ``on_done`` is
        called with the result (or exception) on the UI thread."""
        if self._busy:
            self._set_status("Busy — please wait for the current operation to finish.",
                             severity="warning")
            return

        self._busy = True
        self._set_busy(True)
        self._set_status(label)

        def _worker():
            try:
                result = fn()
                error = None
            except Exception as exc:  # noqa: BLE001 — surfaced to UI
                log.exception("Async operation failed: %s", label)
                result = None
                error = exc
            # Marshal back to the UI thread — Tk is not thread-safe.
            self.after(0, lambda: self._async_complete(on_done, result, error))

        threading.Thread(target=_worker, daemon=True).start()

    def _async_complete(self, on_done, result, error):
        self._busy = False
        self._set_busy(False)
        if error is not None:
            self._set_status(f"Error: {error}", severity="error")
            return
        if callable(on_done):
            try:
                on_done(result)
            except Exception as exc:  # noqa: BLE001 — don't let callback exceptions leak
                log.exception("Async on_done callback raised: %s", exc)
                self._set_status(f"Error: {exc}", severity="error")

    def _set_busy(self, busy: bool):
        """Disable the sidebar's destructive buttons while a background
        operation is running."""
        for btn in (self.import_button, self.delete_button, self.restore_button):
            try:
                btn.configure(state="disabled" if busy else "normal")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Window-state persistence
    # ------------------------------------------------------------------

    def _load_window_state(self):
        try:
            with open(_SETTINGS_PATH, "r", encoding="utf-8") as fh:
                state = json.load(fh)
        except (OSError, ValueError, json.JSONDecodeError):
            return

        if not isinstance(state, dict):
            return
        geom = state.get("geometry")
        if isinstance(geom, str) and geom:
            try:
                self.geometry(geom)
            except Exception:
                pass
        mode = state.get("mode")
        if mode == "mixer":
            self._enter_mixer_mode()
        elif mode == "studio":
            self._enter_studio_mode()
        # preset is the default — no-op
        # Auto-select the last selected theme, if it still exists.
        last_theme = state.get("selected_theme")
        if last_theme and last_theme in self.theme_manager.get_all_themes():
            try:
                self._on_theme_selected(last_theme)
            except Exception:
                pass

    def _save_window_state(self):
        try:
            state = {
                "geometry": self.geometry(),
                "mode": self._mode,
                "selected_theme": self.selected_theme,
            }
            os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
            with open(_SETTINGS_PATH, "w", encoding="utf-8") as fh:
                json.dump(state, fh, indent=2)
        except Exception as exc:  # noqa: BLE001 — persistence is best-effort
            log.warning("Could not save window state: %s", exc)

    def _on_close(self):
        self._save_window_state()
        self.destroy()

    # ------------------------------------------------------------------
    # Keyboard shortcuts
    # ------------------------------------------------------------------

    def _bind_shortcuts(self):
        # Ctrl+1/2/3 — switch modes
        self.bind("<Control-1>", lambda _e: self._enter_preset_mode())
        self.bind("<Control-2>", lambda _e: self._enter_mixer_mode())
        self.bind("<Control-3>", lambda _e: self._enter_studio_mode())
        # Ctrl+Shift+R — reset the UI palette to the built-in default
        # (escape hatch for a theme that renders the UI invisible)
        self.bind("<Control-Shift-R>", lambda _e: self._reset_palette())
        # Ctrl+S — save the current mix (only meaningful in mixer mode)
        self.bind("<Control-s>", lambda _e: self._save_mix_shortcut())

    def _reset_palette(self):
        self.colors.reset_to_default()
        self._set_status("UI palette reset to default", severity="warning")

    def _save_mix_shortcut(self):
        if self._mode == "mixer":
            try:
                self.mix_recipe_panel.do_save()
            except Exception as exc:  # noqa: BLE001 — keep shortcut silent on failure
                log.warning("Save-mix shortcut failed: %s", exc)
                self._set_status(f"Save mix failed: {exc}", severity="error")

    # ------------------------------------------------------------------
    # Shared UI helpers
    # ------------------------------------------------------------------

    def _show_result(self, result: dict):
        if not isinstance(result, dict):
            result = {"success": False, "message": str(result)}

        p = self.colors.palette

        # Reuse a single result dialog: destroy any prior instance before
        # creating a new one.  Prevents stacked modal grabs when Apply
        # Selected fires multiple results in quick succession.
        if self._result_dialog is not None:
            try:
                if self._result_dialog.winfo_exists():
                    self._result_dialog.destroy()
            except Exception:
                pass
            self._result_dialog = None

        dialog = ctk.CTkToplevel(self)
        self._result_dialog = dialog
        dialog.title("Result")
        dialog.geometry("460x240")
        dialog.configure(fg_color=p["background"])
        dialog.transient(self)
        dialog.grab_set()
        # Escape closes the dialog — power users live on the keyboard.
        dialog.bind("<Escape>", lambda _e: dialog.destroy())

        success = bool(result.get("success"))
        icon = "\u2713" if success else "\u2717"  # ✓ / ✗
        color = p["success"] if success else p["error"]

        # Status icon label
        ctk.CTkLabel(
            dialog, text=icon,
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=color,
        ).pack(pady=(20, 0))

        ctk.CTkLabel(
            dialog, text=result.get("message", ""),
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=p["text"], wraplength=420, justify="left",
        ).pack(expand=True, padx=24, pady=(8, 16))

        # Primary / primary_fg: fall back to active / background if the
        # palette hasn't been extended with explicit primary keys (it
        # hasn't in the current core/theme_colors.py contract).
        primary = p.get("primary", p["active"])
        primary_fg = p.get("primary_fg", p["background"])

        ctk.CTkButton(
            dialog, text="OK",
            fg_color=primary, text_color=primary_fg,
            hover_color=p["border"], corner_radius=0,
            command=dialog.destroy,
        ).pack(pady=(0, 16))

    def _set_status(self, message: str, severity: str = "info"):
        """Update the status bar.  ``severity`` colour-codes the bar:
        info (default) / success / warning / error.  Single-arg callers
        see no change."""
        try:
            self.status_label.configure(text=message)
        except Exception:
            # Widget may have been torn down during shutdown.
            return
        try:
            p = self.colors.palette
            if severity == "success":
                fg = p["success"]
            elif severity == "error":
                fg = p["error"]
            elif severity == "warning":
                fg = "#FFB300"
            else:
                fg = p["accent"]
            self.status_bar.configure(fg_color=fg)
        except Exception:
            pass
        log.info("Status: %s", message)
