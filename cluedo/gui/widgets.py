"""Small reusable Tkinter helpers."""
import tkinter as tk


class Tooltip:
    """Hover tooltip. `text_fn` may be a plain string or a zero-arg callable
    evaluated fresh on every hover, so it can reflect current game state."""

    def __init__(self, widget, text_fn):
        self.widget = widget
        self.text_fn = text_fn
        self.tip = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        text = self.text_fn() if callable(self.text_fn) else self.text_fn
        if not text:
            return
        x = self.widget.winfo_rootx() + 16
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip, text=text, background="#ffffe0", relief="solid", borderwidth=1,
            font=("Segoe UI", 9), justify="left", wraplength=320, padx=6, pady=4,
        )
        label.pack()

    def hide(self, event=None):
        if self.tip is not None:
            self.tip.destroy()
            self.tip = None
