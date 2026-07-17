"""Guide dialog — step-by-step setup instructions with screenshots. Theme-reactive."""

import os
import subprocess

import customtkinter as ctk
from PIL import Image

# Known install paths for common tools
_APP_PATHS = {
    "startallback": [
        r"C:\StartAllBack\StartAllBackCfg.exe",
        r"C:\Program Files\StartAllBack\StartAllBackCfg.exe",
        r"C:\Program Files (x86)\StartAllBack\StartAllBackCfg.exe",
    ],
    "mica": [
        r"C:\Program Files\Mica For Everyone\MicaForEveryone.exe",
        r"C:\Users\{username}\AppData\Local\Programs\MicaForEveryone\MicaForEveryone.exe",
    ],
    "oldnewexplorer": [
        r"C:\Program Files\OldNewExplorer\OldNewExplorerCfg.exe",
        r"C:\Program Files (x86)\OldNewExplorer\OldNewExplorerCfg.exe",
    ],
    "windhawk": [r"C:\Program Files\Windhawk\Windhawk.exe"],
}


def _find_app(app_key):
    username = os.environ.get("USERNAME", "")
    for path in _APP_PATHS.get(app_key, []):
        resolved = path.replace("{username}", username)
        if os.path.exists(resolved):
            return resolved
    return None


class GuideDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, colors, steps, app_name=None):
        super().__init__(parent)
        self.colors = colors
        self.steps = steps
        self._image_refs = []

        self.title(title)
        self.geometry("720x640")
        self.minsize(560, 400)
        self.configure(fg_color=colors.p("background"))
        self.grab_set()
        self.resizable(True, True)
        self._build(title, app_name)

    def _build(self, title, app_name):
        p = self.colors.palette

        # Header
        header = ctk.CTkFrame(self, fg_color=p["accent"], corner_radius=0,
                               border_color=p["border"], border_width=1)
        header.pack(fill="x")

        ctk.CTkLabel(
            header, text=title,
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=p["text"],
        ).pack(side="left", padx=16, pady=12)

        ctk.CTkLabel(
            header, text=f"{len(self.steps)} steps",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=p["border"],
        ).pack(side="left", padx=4, pady=12)

        if app_name:
            app_path = _find_app(app_name)
            btn_text = f"Open {app_name.replace('_', ' ').title()}"
            ctk.CTkButton(
                header, text=btn_text,
                font=ctk.CTkFont(family="Segoe UI", size=10),
                fg_color=p["active"], text_color=p["background"],
                hover_color=p["border"], corner_radius=0, width=140,
                command=lambda ap=app_path: self._launch(ap, app_name),
            ).pack(side="right", padx=12, pady=8)

        # Scrollable steps
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color=p["background"],
            scrollbar_button_color=p["border"],
            scrollbar_button_hover_color=p["text"],
        )
        self.scroll.pack(fill="both", expand=True)

        for i, step in enumerate(self.steps):
            self._build_step_card(i + 1, step)

        # Footer
        footer = ctk.CTkFrame(self, fg_color=p["accent"], corner_radius=0,
                               border_color=p["border"], border_width=1)
        footer.pack(fill="x", side="bottom")

        ctk.CTkButton(
            footer, text="Done",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            fg_color=p["text"], text_color=p["active"],
            hover_color=p["border"], corner_radius=0,
            command=self.destroy,
        ).pack(side="right", padx=12, pady=8)

    def _build_step_card(self, number, step):
        p = self.colors.palette

        card = ctk.CTkFrame(self.scroll, fg_color=p["card_fg"], corner_radius=0,
                             border_color=p["border"], border_width=1)
        card.pack(fill="x", padx=16, pady=(12, 0))

        title_bar = ctk.CTkFrame(card, fg_color=p["accent"], corner_radius=0)
        title_bar.pack(fill="x")

        ctk.CTkLabel(
            title_bar, text=f"  {number:02d}",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=p["active"], width=36,
        ).pack(side="left", pady=8)

        ctk.CTkLabel(
            title_bar, text=step.get("title", ""),
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=p["text"], anchor="w",
        ).pack(side="left", padx=(4, 16), pady=8, fill="x", expand=True)

        instruction = step.get("instruction", "")
        if instruction:
            ctk.CTkLabel(
                card, text=instruction,
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=p["text"], wraplength=640, justify="left", anchor="w",
            ).pack(fill="x", padx=16, pady=(10, 6))

        image_path = step.get("image")
        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                max_w = 660
                w, h = img.size
                if w > max_w:
                    h = int(h * max_w / w)
                    w = max_w
                img = img.resize((w, h), Image.LANCZOS)
                ctk_img = ctk.CTkImage(light_image=img, size=(w, h))
                self._image_refs.append(ctk_img)
                ctk.CTkLabel(card, image=ctk_img, text="", fg_color=p["background"]).pack(padx=16, pady=(4, 8))
            except Exception:
                pass

        copy_value = step.get("copy_value")
        if copy_value:
            copy_row = ctk.CTkFrame(card, fg_color=p["background"], corner_radius=0,
                                     border_color=p["border"], border_width=1)
            copy_row.pack(fill="x", padx=16, pady=(0, 12))

            ctk.CTkLabel(
                copy_row, text=step.get("copy_label", "Value to copy"),
                font=ctk.CTkFont(family="Segoe UI", size=9),
                text_color=p["border"],
            ).pack(side="left", padx=(10, 4), pady=6)

            ctk.CTkLabel(
                copy_row, text=copy_value,
                font=ctk.CTkFont(family="Segoe UI Mono", size=11, weight="bold"),
                text_color=p["active"],
            ).pack(side="left", padx=4, pady=6)

            ctk.CTkButton(
                copy_row, text="Copy", width=52, height=24,
                font=ctk.CTkFont(family="Segoe UI", size=9),
                fg_color=p["accent"], text_color=p["text"],
                hover_color=p["border"], corner_radius=0,
                command=lambda v=copy_value: self._copy_to_clipboard(v),
            ).pack(side="right", padx=8, pady=6)

    def _copy_to_clipboard(self, value):
        self.clipboard_clear()
        self.clipboard_append(value)
        self.update()

    def _launch(self, app_path, app_key):
        if app_path and os.path.exists(app_path):
            subprocess.Popen([app_path])
        else:
            p = self.colors.palette
            dialog = ctk.CTkToplevel(self)
            dialog.title("App Not Found")
            dialog.geometry("360x140")
            dialog.configure(fg_color=p["background"])
            dialog.transient(self)
            dialog.grab_set()
            ctk.CTkLabel(
                dialog,
                text=f"Could not find {app_key.title()} in common install locations.\nPlease launch it manually.",
                font=ctk.CTkFont(family="Segoe UI", size=11),
                text_color=p["text"], wraplength=320, justify="center",
            ).pack(expand=True, padx=20, pady=20)

            def _on_ok():
                dialog.destroy()
                # Restore the parent GuideDialog's modal grab — Tk does
                # not auto-re-grab after a sub-dialog closes, so without
                # this the user could interact with the main window
                # behind the still-open guide.
                if self.winfo_exists():
                    try:
                        self.grab_set()
                    except Exception:
                        pass

            ctk.CTkButton(
                dialog, text="OK", corner_radius=0,
                fg_color=p["accent"], text_color=p["text"],
                hover_color=p["border"], command=_on_ok,
            ).pack(pady=(0, 16))