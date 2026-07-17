"""Lightweight hover tooltip — no external dependencies.

A minimal Hovertip implementation built directly on ``tk.Toplevel``.
Shows a small floating label near a widget after the pointer has been
resting on it for ``hover_delay`` milliseconds; hides on ``<Leave>``
or ``<Button-1>``.  Designed to be robust against the parent widget
being destroyed while a show is pending (every callback guards with
``winfo_exists``).

Public API::

    tip = Hovertip(widget, "Tooltip text", hover_delay=500)

The tooltip tracks the parent widget's lifetime: when the widget is
destroyed the scheduled show is cancelled and any open tip window is
torn down.
"""

from __future__ import annotations

import tkinter as tk


class Hovertip:
    """Minimal hover tooltip bound to a single widget.

    Parameters
    ----------
    widget:
        Any ``tk.Widget`` (or subclass, incl. ``customtkinter`` widgets)
        that the tooltip is attached to.
    text:
        The tooltip message.  May contain newlines.
    hover_delay:
        Milliseconds the pointer must rest on the widget before the
        tooltip appears.  Default 500 ms.
    """

    def __init__(self, widget: tk.Widget, text: str, hover_delay: int = 500):
        self._widget = widget
        self._text = text
        self._hover_delay = hover_delay
        self._tip: tk.Toplevel | None = None
        self._after_id: str | None = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<Button-1>", self._hide, add="+")
        # Tear down the tip when the widget itself is destroyed so we
        # never leave an orphan Toplevel on screen.
        widget.bind("<Destroy>", self._on_destroy, add="+")

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def configure(self, text: str | None = None) -> None:
        """Update the tooltip text (and refresh an open tip if visible)."""
        if text is not None:
            self._text = text
        if self._tip is not None and self._tip.winfo_exists():
            for child in self._tip.winfo_children():
                child.configure(text=self._text)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _on_enter(self, event=None) -> None:
        self._schedule()

    def _on_leave(self, event=None) -> None:
        self._cancel_schedule()
        self._hide()

    def _on_destroy(self, event=None) -> None:
        self._cancel_schedule()
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None

    # ------------------------------------------------------------------
    # Schedule / show / hide
    # ------------------------------------------------------------------

    def _schedule(self) -> None:
        self._cancel_schedule()
        try:
            self._after_id = self._widget.after(self._hover_delay, self._show)
        except Exception:
            # Widget may have been destroyed between bind and after().
            self._after_id = None

    def _cancel_schedule(self) -> None:
        if self._after_id is not None:
            try:
                self._widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        # Guard against the widget being destroyed while the show was
        # pending — Tk raises TclError on a stale widget reference.
        try:
            if not self._widget.winfo_exists():
                return
            x = self._widget.winfo_rootx() + 20
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4
        except Exception:
            return

        if self._tip is not None and self._tip.winfo_exists():
            self._tip.destroy()
            self._tip = None

        tip = tk.Toplevel(self._widget)
        tip.wm_overrideredirect(True)
        try:
            tip.transient(self._widget)
        except Exception:
            pass
        tip.wm_geometry(f"+{x}+{y}")
        # Keep the tooltip from stealing focus / appearing in the taskbar.
        tip.attributes("-topmost", True)

        # Pull colours from the parent widget so the tip inherits the
        # active theme palette when attached to a themed CTk widget.
        bg = "#2b2b2b"
        fg = "#ffffff"
        try:
            bg = self._widget.cget("fg_color") or bg
        except Exception:
            pass
        # CTk returns a tuple (light, dark) for fg_color — pick the dark one.
        if isinstance(bg, (tuple, list)) and bg:
            bg = bg[-1] if len(bg) > 1 else bg[0]

        label = tk.Label(
            tip, text=self._text, justify="left",
            background=bg, foreground=fg, relief="solid", borderwidth=1,
            padx=6, pady=2, font=("Segoe UI", 9),
        )
        label.pack()

        self._tip = tip

    def _hide(self, event=None) -> None:
        if self._tip is not None:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None
